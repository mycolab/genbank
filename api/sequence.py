import os
import hashlib
import json
import yaml
import xmltodict
import logging
from operator import itemgetter
from subprocess import Popen, PIPE
from xml.parsers.expat import ExpatError


def log_results(results: list):
    """
    Log command results
    :param results:
    :return:
    """
    for result in results:
        for k, v in result.items():
            if isinstance(v, (bytes, bytearray)):
                v = v.decode('utf-8')
            msg = {k: v}
            if k == 'stdout' and v != '':
                logging.info(msg)
            if k == 'stderr' and v != '':
                logging.error(msg)


def execute(commands: list) -> list:
    """
    Function that executes a series of command strings, and raises exception on failure
    :param commands: list of command strings
    """
    results = []
    for command in commands:
        p = Popen(command, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True)
        stdout, stderr = p.communicate()
        if p.returncode == 1:
            raise SystemExit()
        result = {'command': command, 'stdout': stdout, 'stderr': stderr}
        results.append(result)
    return results


def get_id(body: dict) -> str:
    """
    Generate Id from hash of body
    :param body:
    :return:
    """
    body_str = json.dumps(body)
    return hashlib.md5(body_str.encode('utf-8')).hexdigest()


def load_xml(file: str) -> dict:
    """
    Return dictionary from XML file
    :param file:
    :return:
    """

    with open(file) as f:
        data = xmltodict.parse(f.read())
        f.close()

    return data


def load_json(file: str) -> dict:
    """
    Return dictionary from JSON file
    :param file:
    :return:
    """

    with open(file) as f:
        data = json.load(f)
        f.close()

    return data


def write_json(data: dict, file: str):
    """
    Write JSON file from dict
    :param data:
    :param file:
    :return:
    """

    with open(file, 'w') as f:
        json.dump(data, f)


def write_file(file: str, lines: list):
    """
    Write file from list of lines
    :param file:
    :param lines:
    :return:
    """

    f = open(file, "w")  # append mode
    f.writelines(lines)
    f.close()


def load_blast_hits(blast_results: dict) -> list:
    """
    Return list of accession dictionaries from blastn results
    :param blast_results:
    :return:
    """

    report = blast_results['BlastOutput2'][0]['report']
    hits = report['results']['search']['hits']
    query_len = report['results']['search']['query_len']

    # build accessions from hits
    blast_hits = []
    for hit in hits:
        accession_number = hit['description'][0]['accession']
        accession_ids = str(hit['description'][0]['id']).split('|')
        accession_id = accession_number
        for element in accession_ids:
            if accession_number in element:
                accession_id = element

        description = hit['description'][0]['title']
        hsp = hit['hsps'][0]
        align_len = hsp['align_len']
        identity = hsp['identity']
        gaps = hsp['gaps']

        blast_hit = {
            'id': accession_id,
            'description': description,
            'pct_identity': (identity / align_len) * 100,
            'coverage': ((align_len - gaps) / query_len) * 100,
            **hsp
        }

        logging.debug(json.dumps(blast_hit))
        blast_hits.append(blast_hit)

    return blast_hits


def fetch_accession(xml_file: str, accession_id: str) -> int:
    try:
        efetch_command = f'/usr/local/bin/efetch -db nuccore -id {accession_id} -format gb -mode xml > {xml_file}'
        command_results = execute([efetch_command])
        log_results(command_results)
        resp_code = 0
    except SystemExit as e:
        logging.warning(str(e))
        resp_code = 1

    return resp_code


def clean_fasta(fasta_sequence: str, remove_gaps: bool = True) -> dict:
    """
    Clean FASTA sequence
    :param fasta_sequence:
    :param remove_gaps:
    :return:
    """

    lines = fasta_sequence.splitlines()
    description = ''
    seq = []
    for line in lines:
        if '>' in line:
            description = line
        else:
            seq.append(line)

    sequence = ''.join(seq)

    gap_chars = ['-', '.']

    if remove_gaps:
        for gap_char in gap_chars:
            logging.debug(f'removing gap char: "{gap_char}", from: {sequence}')
            sequence = sequence.replace(gap_char, '')
            logging.debug(f'clean_sequence: {sequence}')

    fasta = {'description': description, 'sequence': sequence}

    return fasta


def load_countries() -> dict:
    """
    Loads counties.yaml as dictionary
    :return:
    """

    countries = {}
    this_dir = os.path.dirname(os.path.realpath(__file__))
    countries_file = f'{this_dir}/countries.yaml'

    with open(countries_file, "r") as stream:
        try:
            countries = yaml.safe_load(stream)
        except yaml.YAMLError as e:
            logging.error(e)

    logging.debug(json.dumps(countries))

    return countries


def country_search(countries: dict = None, location_data: str = None) -> str:
    """
    Approximates country of origin
    :param countries:
    :param location_data:
    :return:
    """

    country = ''
    approx_char = '*'

    if countries:

        for key, value in countries.items():
            if key in location_data:
                country = key
                break

        if country == '':
            for key, value in countries.items():
                alts = value.get('alts', None)

                if alts:
                    for alt in alts:
                        if alt in location_data:
                            country = key
                            break
                    if country != '':
                        break

        if country == '':
            for key, value in countries.items():
                alpha_3 = value.get('alpha_3')

                if f' {alpha_3} ' in location_data or f'{alpha_3}:' in location_data:
                    country = f'{approx_char}{key}'
                    break

    if country == '':
        logging.warning(f'NO COUNTRY DATA FOUND: {location_data}')
    else:
        country = f'{approx_char}{country}'

    return country


def load_fasta(
        id: str,
        blast_hits: list,
        add_location: bool = True,
        remove_gaps: bool = True,
        include_accession: bool = False,
        include_hsp: bool = False) -> list:
    """
    Return list of fasta dictionaries from blast hits
    :param id:
    :param blast_hits: list of blast hits
    :param add_location:
    :param remove_gaps:
    :param include_accession:
    :param include_hsp:
    :return:
    """

    fastas = []

    # pre-load countries dictionary
    countries = {}
    if add_location:
        countries = load_countries()

    # run efetch to pull all accession details
    for blast_hit in blast_hits:
        accession_id = blast_hit.get('id')
        hsp = {**blast_hit}

        xml_file = f'/blast/fasta/{id}.{accession_id}.xml'
        json_file = f'/blast/fasta/{id}.{accession_id}.json'

        skip = False
        # fetch accession from Genbank
        if fetch_accession(xml_file, accession_id) > 0:
            skip = True

        # load results to a_object
        a_object = {}
        if not skip:
            try:
                a_object = load_xml(xml_file)
                write_json(a_object, json_file)
            except ExpatError as e:
                logging.warning(str(e))
                skip = True

        # create fasta dictionary
        if not skip:
            try:
                organism = a_object['GBSet']['GBSeq']['GBSeq_organism']
                description = f'{accession_id} {organism}'

                if add_location:
                    location = None
                    qualifiers = a_object['GBSet']['GBSeq']['GBSeq_feature-table']['GBFeature'][0]['GBFeature_quals']['GBQualifier']
                    for qualifier in qualifiers:
                        if 'country' in qualifier.get('GBQualifier_name'):
                            location = qualifier.get('GBQualifier_value')
                            if location != '' and location is not None:
                                break

                    if location is None or location == '':
                        location = country_search(countries=countries, location_data=json.dumps(a_object))

                    if location:
                        a_object['location'] = location
                        description += f' {location}'

                # full sequence
                sequence = a_object['GBSet']['GBSeq']['GBSeq_sequence']

                # remove gaps, conditionally
                sequence = clean_fasta(sequence, remove_gaps=remove_gaps).get('sequence')

                # add fasta to results
                fasta = {'description': description, 'sequence': sequence}

                if include_accession:
                    fasta = {**fasta, 'accession': a_object}

                if include_hsp:
                    fasta = {**fasta, 'hsp': hsp}

                fastas.append(fasta)

            except KeyError as e:
                logging.error(f'{e}')

        # clean up files
        for file in [xml_file, json_file]:
            if os.path.exists(file):
                os.remove(file)
            else:
                logging.warning(f'file does not exist: {file}')

    return fastas


def mycolab_stamp(description: str, mycolab_id: str = None) -> str:
    """
    Prefix FASTA description with MycoLab ID
    :param description:
    :param mycolab_id:
    :return:
    """

    mycolab_name = 'MycoLab'
    if mycolab_id:
        # truncate Id to 10 chars
        mycolab_name = f'{mycolab_name}-{mycolab_id[0:10]}'

    # prep by removing '>'
    description = description.replace('>', '')

    # prefix with MycoLab stamp
    if len(description) > 0:
        description = f'{mycolab_name} {description}'
    else:
        description = f'{mycolab_name}'

    return description


def sort_blast_hits(blast_hits: list = None, sort_keys: list = None, direction: str = 'desc'):
    """
    Sort blast hits
    :param blast_hits: list of blast hit objects
    :param sort_keys: list of object keys names
    :param direction: string: 'asc' or 'desc'
    :return:
    """

    dir_map = {
        'asc': False,
        'desc': True
    }

    sorted_blast_list = blast_hits

    for sort_key in sort_keys:
        sorted_blast_list = sorted(sorted_blast_list, key=itemgetter(sort_key), reverse=dir_map[direction])

    return sorted_blast_list


def filter_blast_hits(blast_hits: list = None, filter_objs: list = None):
    """
    Sort blast hits
    :param blast_hits: list of blast hit objects
    :param filter_objs: list of filter objects
    :return:
    """

    if not filter_objs:
        filter_objs = [
            {
                'key': 'coverage',
                'min': 70
            }
        ]

    filtered_blast_list = blast_hits

    for f in filter_objs:
        k = f['key']
        if 'min' in f.keys():
            f_min = f['min']
            if 'max' in f.keys():
                f_max = f['max']
                filtered_blast_list = list(filter(lambda b: f_min <= b[k] <= f_max, blast_hits))
            else:
                filtered_blast_list = list(filter(lambda b: f_min <= b[k], blast_hits))
        else:
            v = f['value']
            m = f.get('mod', None)
            filtered_blast_list = list(filter(lambda b: b[k] + m in v if m is not None else b[k] in v, blast_hits))

    return filtered_blast_list


def query(body: dict = None, **kwargs):
    """
    Query Genbank for matching sequences
    :param body: query options
      Example:
      {
        "location": true,
        "match": 98.5,
        "results": 100,
        "sequence": "ACTAtGttGCCTtGGCAGGCTGGCAGCAGCCTGCCGGTGGACCTCAACTCTTGAATCTCTG..."
      }
    :param kwargs:
    :return: list of fasta sequence dicts
      Example:
      [
        {
          "description": "MK373018.1 Cudonia confusa USA",
          "sequence": "ACTATGTTGCCTTGGCAGGCTGGCAGCAGCCTGCCGGTGGACCTCAACTCTTGAATCTCT..."
        }
      ]
    """
    logging.debug(f'kwargs: {kwargs}')

    # generate Id from body
    id = get_id(body)

    # location enrichment
    add_location = body.get('location', True)

    # alignment gap removal
    remove_gaps = body.get('clean', True)

    # include accession in FASTA object
    include_accession = body.get('accession', False)

    # include blast hsp in FASTA object
    include_hsp = body.get('hsp', False)

    # add mycolab stamp
    add_stamp = body.get('stamp', True)

    # maximum results
    max_results = body.get('results', 50)

    # minimum identity match
    min_match = body.get('match', 90.0)

    # sort results by key
    sort_key = body.get('sort_key', 'pct_identity')

    # sort direction
    sort_dir = body.get('sort_dir', 'desc')

    # minimum coverage
    min_coverage = body.get('coverage', 70.0)

    # clean fasta query
    query_fasta = clean_fasta(body.get('sequence'), remove_gaps=remove_gaps)
    query_description = query_fasta.get('description')
    query_sequence = query_fasta.get('sequence')
    logging.debug(f'"query_description": "{query_description}", "query_sequence": {query_sequence}')

    # write fas query
    q_file = f'/blast/queries/{id}.fas'
    write_file(q_file, [query_sequence])

    # set blastn options
    word_size = 28
    output_format = 15  # JSON
    database = 'nt'     # nucleotide
    o_file = f'/blast/fasta/{id}.json'
    option_list = [
        '-remote',
        f'-db {database}',
        f'-word_size {word_size}',
        f'-outfmt {output_format}',
        f'-perc_identity {min_match}',
        f'-max_target_seqs {max_results}',
        f'-query {q_file}',
        f'-out {o_file}'
    ]
    options = ' '.join(option_list)

    # execute blast query
    blastn_command = f'/usr/local/bin/blastn {options}'
    logging.debug(blastn_command)
    command_results = execute([blastn_command])
    log_results(command_results)

    # load accessions from blast output
    blast_results = load_json(o_file)
    blast_hits = load_blast_hits(blast_results)
    blast_hits = sort_blast_hits(blast_hits, sort_keys=[sort_key], direction=sort_dir)
    blast_hits = filter_blast_hits(blast_hits, filter_objs=[{'key': 'coverage', 'min': min_coverage}])

    # load fasta from accessions
    resp = load_fasta(
        id,
        blast_hits,
        add_location=add_location,
        remove_gaps=remove_gaps,
        include_accession=include_accession,
        include_hsp=include_hsp
    )

    # conditionally add MycoLab stamp
    if add_stamp:
        description = mycolab_stamp(query_description, mycolab_id=id)
    else:
        description = query_description

    # insert query fasta as first record
    mycolab_fasta = {'description': description, 'sequence': query_sequence}
    resp.insert(0, mycolab_fasta)

    # write original query to disk
    write_json(body, f'/blast/fasta/mycolab-query-{id}.json')

    # clean up temp files
    for file in [q_file, o_file]:
        if os.path.exists(file):
            os.remove(file)
        else:
            logging.warning(f'file does not exist: {file}')

    return resp, 200


# todo: add _local_ genbank API sequence methods
# sequence API method stubs
def post(body: dict = None, **kwargs):
    logging.debug(f'kwargs: {kwargs}')
    id = get_id(body)
    resp = {
        'id': id
    }
    return resp, 200


def put(id: str = None, body: dict = None, **kwargs):
    params = {
        'id': id,
        'body': body,
        'kwargs': kwargs
    }
    logging.debug(f'{params}')
    pass


def get(id: str = None, **kwargs):
    params = {
        'id': id,
        'kwargs': kwargs
    }
    logging.debug(f'{params}')
    pass


def delete(id: str = None, **kwargs):
    params = {
        'id': id,
        'kwargs': kwargs
    }
    logging.debug(f'{params}')
    pass
