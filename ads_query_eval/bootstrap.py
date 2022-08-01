from typing import Callable

from pymongo import ReplaceOne
from pymongo.database import Database as MongoDatabase

from ads_query_eval.config import get_mongo_db
from ads_query_eval.models import Query, QueryTopicReviews

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
    #'similar(bibcode:2015AdSpR..55.2745S)',
    #'useful(topn(200,similar(1958ApJ...128..664P)))',
    #'useful(topn(200,similar(1961PhRvL...6...47D)))',
    #'trending(full:"space weather")'
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
}


def _bootstrap_queries():
    coll_ops = []
    for i, query in enumerate(QUERIES):
        q = Query(id=str(i + 1), query=query, run_ids=[])
        coll_ops.append(
            ReplaceOne(filter={"query": q.query}, replacement=q.dict(), upsert=True)
        )
    db = get_mongo_db()
    db.queries.create_index("query", unique=True)
    db.queries.create_index("id", unique=True)
    db.queries.bulk_write(coll_ops)


def _bootstrap_query_topic_reviews():
    coll_ops = []
    for query, bibcodes in QUERY_TOPIC_REVIEWS.items():
        q = QueryTopicReviews(query=query, bibcodes=bibcodes)
        coll_ops.append(
            ReplaceOne(filter={"query": q.query}, replacement=q.dict(), upsert=True)
        )
    db = get_mongo_db()
    db.query_topic_reviews.bulk_write(coll_ops)


def bootstrap():
    _bootstrap_queries()
    _bootstrap_query_topic_reviews()
