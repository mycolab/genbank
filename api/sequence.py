import hashlib
import json
import xmltodict
import logging
from subprocess import Popen, PIPE


def log_results(results: list):
    """
    Log results
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
    Function that runs a series of command string,
    raises exception on failure
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
    body_str = json.dumps(body)
    return hashlib.md5(body_str.encode('utf-8')).hexdigest()


def load_xml(file: str) -> dict:

    with open(file) as f:
        data = xmltodict.parse(f.read())
        f.close()

    return data


def load_json(file: str) -> dict:

    with open(file) as f:
        data = json.load(f)
        f.close()

    return data


def write_json(data: dict, file: str):

    with open(file, 'w') as f:
        json.dump(data, f)


def write_file(file: str, lines: list):
    f = open(file, "w")  # append mode
    f.writelines(lines)
    f.close()


def load_accessions(blast_results: dict) -> list:
    report = blast_results['BlastOutput2'][0]['report']
    hits = report['results']['search']['hits']

    # build accessions from hits
    accessions = []
    for hit in hits:
        accession_number = hit['description'][0]['accession']
        accession_ids = str(hit['description'][0]['id']).split('|')
        accession_id = accession_number
        for element in accession_ids:
            if accession_number in element:
                accession_id = element

        description = hit['description'][0]['title']
        hit_sequence = hit['hsps'][0]['hseq']
        accession = {'id': accession_id, 'description': description, 'sequence': hit_sequence}
        print(json.dumps(accession))
        accessions.append(accession)

    return accessions


def fetch_accession(xml_file: str, accession_id: str):
    efetch_command = f'/usr/local/bin/efetch -db nuccore -id {accession_id} -format gb -mode xml > {xml_file}'
    command_results = execute([efetch_command])
    log_results(command_results)


def load_fastas(id: str, accessions: list) -> list:

    fastas = []
    # run efetch to pull all accession details
    for accession in accessions:
        accession_id = accession['id']
        xml_file = f'/blast/fasta/{id}.{accession_id}.xml'
        json_file = f'/blast/fasta/{id}.{accession_id}.json'
        fetch_accession(xml_file, accession_id)
        a_object = load_xml(xml_file)
        write_json(a_object, json_file)
        fastas.append({'description': accession['description'], 'sequence': accession['sequence']})

    return fastas


def query(body: dict = None, **kwargs):
    """
    :param body:
      Example:
      {
        "location": true,
        "match": 98.5,
        "results": 100,
        "sequence": "ACTAtGttGCCTtGGCAGGCTGGCAGCAGCCTGCCGGTGGACCTCAACTCTTGAATCTCTG..."
      }
    :param kwargs:
    :return:
      Example: http://jsonblob.com/930240229424775168
    """

    id = get_id(body)
    query_sequence = body['sequence']

    # maximum results
    results = 20
    if 'results' in body.keys():
        results = body['results']

    # minimum identity match
    match = 95
    if 'match' in body.keys():
        match = body['match']

    # minimum identity match
    location = True
    if 'location' in body.keys():
        location = body['location']

    # write fas query
    q_file = f'/blast/queries/{id}.fas'
    write_file(q_file, [query_sequence])

    # set blastn options
    o_file = f'/blast/fasta/{id}.json'
    options = f'-remote -db nt -word_size 28 -outfmt 15 -perc_identity {match} -max_target_seqs {results}'

    # run blastn command
    blastn_command = f'/usr/local/bin/blastn {options} -query {q_file} -out {o_file}'
    command_results = execute([blastn_command])
    log_results(command_results)

    # load accessions from blast output
    blast_results = load_json(o_file)
    accessions = load_accessions(blast_results)

    # load fasta from accessions
    resp = load_fastas(id, accessions)

    return resp, 200


def post(body: dict = None, **kwargs):
    id = get_id(body)
    resp = {
        'id': id
    }
    return resp, 200


def put(id: str = None, body: dict = None, **kwargs):
    pass


def get(id: str = None, **kwargs):
    pass


def delete(id: str = None, **kwargs):
    pass
