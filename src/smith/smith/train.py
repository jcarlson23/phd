#
# Train machine learning models on dataset.
#
#   Include only preprocessed files in training set with unique md5s
#
#   ML:
#
#     Train char-rnn on raw text
#     Train char-rnn on files which compiled
#     Train char-rnn on "cleaned" text (no comments, etc)
#     Train char-rnn on bytecode
#     Train char-rnn on AST(?)
import os
import re
import sqlite3
import sys

from argparse import ArgumentParser

import smith
from smith import dbutil


def sanitize_id(id):
    return re.sub('[/:\.]+', '-', id)


def create_corpus(db, out_path, gh=False, fileid=False, reverse=False,
                  input_samples=False, status=0, eof=False, dir=False):
    # Dump all the preprocessed OpenCL files
    print('creating DNN corpus', out_path, '...')

    order = 'ASC' if reverse else 'DESC'

    c = db.cursor()

    # Query components
    table = 'ContentFiles' if input_samples else 'PreprocessedFiles'
    select = 'SELECT {}.id,{}.contents'.format(table, table, table)

    if input_samples:
        qualifier = ''
    else:
        qualifier = 'WHERE {}.status={}'.format(table, status)

    if gh:
        table += (' LEFT JOIN ContentMeta ON {}.id=ContentMeta.id'
                  ' LEFT JOIN Repositories ON '
                  'ContentMeta.repo_url=Repositories.url'
                  .format(table))
        orderby = 'Repositories.stars'
    else:
        orderby = 'LC(contents)'

    query = ('{select} FROM {table} {qualifier} ORDER BY {orderby} {order}'
             .format(select=select, table=table, qualifier=qualifier,
                     orderby=orderby, order=order))

    c.execute(query)
    rows = c.fetchall()

    if dir:
        print('writing to directory ', out_path, '/', sep='')
        if os.path.exists(out_path):
            print('fatal: directory already exists!', file=sys.stderr)
            return 1
        else:
            os.makedirs(out_path)
            for row in rows:
                id,contents = row
                path = os.path.join(out_path, sanitize_id(id) + '.cl')
                with open(path, 'w') as out:
                    out.write(contents)
            return 0
    else:
        print('writing file', out_path)
        with open(out_path, 'w') as out:
            for row in rows:
                id,contents = row
                if fileid: # Print file ID
                    out.write('/* ID: {} */\n\n'.format(id))
                out.write(contents)
                if eof: # Print EOF token
                    out.write('\n/* EOF */\n\n')
                else:
                    out.write('\n\n')
        return 0


def linecount(t):
    return len(t.split('\n'))


def train(db_path, out_path, **kwargs):
    db = sqlite3.connect(db_path)
    db.create_function("LC", 1, linecount)

    # auto-detect whether it's a GitHub repo
    kwargs['gh'] = dbutil.is_github(db)

    ret = create_corpus(db, out_path, **kwargs)
    if ret:
        sys.exit(ret)
