from pymongo import ReplaceOne
from terminusdb_client import WOQLClient
from toolz import pluck

from ads_query_eval.config import get_terminus_client, get_terminus_config
from ads_query_eval.lib.util import hash_of

QUERIES = (
    'full:"coronal mass ejection"',
    'full:"solar wind"',
    'full:"ionospheric_conductivity"',
    'full:"space weather"',
    'full:"geomagnetically induced current"',
    'full:("solar wind" AND magnetosphere AND coupling)',
    "full:(magnetosphere AND ionosphere AND coupling)",
    'full:("interplanetary magnetic field" AND reconnection)',
    'full:"substorm"',
    'full:"particle acceleration"',
    "similar(bibcode:2015AdSpR..55.2745S)",
    "useful(topn(200,similar(1958ApJ...128..664P)))",
    "useful(topn(200,similar(1961PhRvL...6...47D)))",
    'trending(full:"space weather")',
)

QUERY_TOPIC_REVIEWS = {
    'full:"coronal mass ejection"': [
        "bibcode:2017LRSP...14....5K",
        "bibcode:2012LRSP....9....3W",
    ],
    'full:"solar wind"': ["bibcode:2021LRSP...18....3V"],
    'full:"ionospheric_conductivity"': [
        "bibcode:1993JATP...55.1493B",
        "bibcode:2008AnGeo..26.3913A",
        "bibcode:2012GMS...197..143M",
        "bibcode:1956NCim....4S1385C",
    ],
    'full:"space weather"': [
        "bibcode:2006LRSP....3....2S",
        "bibcode:2021LRSP...18....4T",
        "bibcode:2007LRSP....4....1P",
        "bibcode:2015AdSpR..55.2745S",
        "bibcode:2022FrASS...8..253B",
    ],
    'full:"geomagnetically induced current"': [
        "bibcode:2017SpWea..15..828P",
        "bibcode:2017SpWea..15..258B",
    ],
    'full:("solar wind" AND magnetosphere AND coupling)': [
        "bibcode:2021LRSP...18....3V",
        "bibcode:2007LRSP....4....1P",
        "bibcode:2022FrASS...908629D",
    ],
    "full:(magnetosphere AND ionosphere AND coupling)": [
        "bibcode:2007LRSP....4....1P",
        "bibcode:2008SSRv..139..235W",
    ],
    'full:("interplanetary magnetic field" AND reconnection)': [
        "bibcode:2012SSRv..172..187G",
        "bibcode:2011SSRv..160...95F",
        "bibcode:2021LRSP...18....3V",
    ],
    'full:"substorm"': ["bibcode:2015SSRv..190....1K"],
    'full:"particle acceleration"': [
        "bibcode:2012SSRv..173..433F",
        "bibcode:2012SSRv..173..103M",
    ],
    "similar(bibcode:2015AdSpR..55.2745S)": [
        "bibcode:2006LRSP....3....2S",
        "bibcode:2021LRSP...18....4T",
        "bibcode:2007LRSP....4....1P",
        "bibcode:2018SSRv..214...21R",
    ],
    "useful(topn(200,similar(1958ApJ...128..664P)))": [
        "bibcode:2021LRSP...18....3V",
        "bibcode:2012SSRv..173..433F",
    ],
    "useful(topn(200,similar(1961PhRvL...6...47D)))": [
        "bibcode:2007LRSP....4....1P",
        "bibcode:2018SSRv..214...17B",
        "bibcode:2004SpWea...211004T",
        "bibcode:2015SSRv..190....1K",
    ],
    'trending(full:"space weather")': [
        "bibcode:2022LRSP...19....2C",
        "bibcode:2021ARA&A..59..445H",
        "bibcode:2015AdSpR..55.2745S",
        "bibcode:2007LRSP....4....1P",
        "bibcode:2021PEPS....8...21S",
    ],
}


def _bootstrap_db():
    config = get_terminus_config()
    _client = WOQLClient(server_url=config["server_url"])
    _client.connect(user="admin", key=config["admin_pass"])
    exists = _client.get_database(config["dbid"])
    if exists and config["force_reset_on_init"]:
        _client.delete_database(dbid=config["dbid"], team="admin", force="true")
    exists = _client.get_database(config["dbid"])
    if not exists:
        print("bootstrapping terminus db")
        _client.create_database(config["dbid"], team="admin")
        _client.replace_document(
            config["schema_objects"],
            graph_type="schema",
            commit_msg="Adding schema",
            create=True,
        )
    elif config.get("reset_schema"):
        _client.replace_document(
            config["schema_objects"],
            graph_type="schema",
            commit_msg="Resetting schema",
            create=True,
        )


def _bootstrap_queries():
    client = get_terminus_client()
    missing = set(QUERIES) - set(
        pluck("query_literal", client.get_documents_by_type("Query"))
    )
    if missing:
        client.insert_document(
            [
                {
                    "query_literal": q,
                    "@type": "Query",
                }
                for q in missing
            ],
            commit_msg="Ensure queries",
        )


def _bootstrap_query_topic_reviews_evaluator():
    client = get_terminus_client()
    exists = {
        (d["fqn"], d["version"])
        for d in client.get_documents_by_type("EvaluatingProcedure")
    }
    to_ensure = {("ads_query_eval.frame.evaluators.topic_review_references", "0.1")}
    missing = to_ensure - exists
    if missing:
        client.insert_document(
            [
                {
                    "@type": "EvaluatingProcedure",
                    "fqn": _fqn,
                    "version": _version,
                    "config": QUERY_TOPIC_REVIEWS,
                }
                for _fqn, _version in missing
            ],
            commit_msg="Ensure evaluator",
        )


def bootstrap():
    _bootstrap_db()
    _bootstrap_queries()
    _bootstrap_query_topic_reviews_evaluator()
