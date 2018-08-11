#!/usr/bin/env python3
import argparse
from getpass import getpass
import json
import logging
import sys
from tempfile import mkstemp
from time import sleep, strftime
import traceback
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED


try:
    from bs4 import BeautifulSoup
except ImportError:
    print('MISSING BeautifulSoup LIBRARY, TRYING TO INSTALL')
    from pip._internal import main as pip_main
    pip_main(['install', 'bs4', 'lxml'])
    from bs4 import BeautifulSoup

try:
    import requests
except ImportError:
    print('MISSING requests LIBRARY, TRYING TO INSTALL')
    from pip._internal import main as pip_main
    pip_main(['install', 'requests'])
    import requests

try:
    import colorama
except ImportError:
    print('MISSING colorama LIBRARY, TRYING TO INSTALL')
    from pip._internal import main as pip_main
    pip_main(['install', 'colorama'])
    import colorama
finally:
    colorama.init(autoreset=True)


DAWANDA_BASEURL = 'https://de.dawanda.com'


def iterate_urls(session, urls, handler, results):
    assert isinstance(urls, list)

    seen_urls = []
    while len(urls) > 0:
        url = urls.pop()
        if url.startswith('/'):
            url = DAWANDA_BASEURL + url
        # silently ignore duplicate URLs
        if url in seen_urls:
            continue

        print('\033[K    ', url[len(DAWANDA_BASEURL):], ' ... ', end='\r', flush=True, sep='')
        req = session.get(url)
        if req.status_code != 200:
            print('Got error', req.status_code, 'loading', url)
            continue

        seen_urls.append(url)

        try:
            more_urls = handler(req.text, results) or []
            for u in more_urls:
                urls.append(u)

        except Exception as err:
            datafilefd, datafilename = mkstemp(prefix='dawanda-', suffix='-page.txt', text=True)
            with open(datafilefd, 'w') as datafile:
                print(traceback.format_exc(), file=datafile)
                print(req.text, file=datafile)
            print('Error parsing URL ({err}), saved debug data to {f}'.format(err=err, f=datafilename))


def parse_product_list(text, products):
    req_page = BeautifulSoup(text, 'lxml')

    prod_table = req_page.find('table', id='product_table')
    if prod_table is None:
        return []

    prod_table_body = prod_table.find('tbody')
    for row in prod_table_body.find_all('tr'):
        cells = row.find_all('td')
        prod_id = cells[0].find('input')['value']
        prod_title = cells[2].find('a')
        prod_title = prod_title.string if prod_title is not None else list(cells[2].stripped_strings)[0]
        prod_sku = cells[2].select_one('div.product-sku')
        prod_sku = prod_sku.string if prod_sku else None
        prod_price = row.select_one('td span.money')

        if prod_id in products:
            print('WARNING: product {id} encountered twice'.format(id=prod_id))

        products[prod_id] = {
            'id': prod_id,
            'sku': prod_sku,
            'title': prod_title,
            'price': {'amount': float(prod_price.select_one('span.amount').string), 'unit': prod_price.select_one('abbr.unit').string}
        }

    return [link['href'] for link in req_page.select('div.pagination > a.next_page')]


def parse_product(text):
    req_page = BeautifulSoup(text, 'lxml')

    product_tag = req_page.select_one('script.product_data')
    product = json.loads(product_tag.string)
    return product


def get_product_list(session):
    products = {}
    urls = [
        DAWANDA_BASEURL + '/seller/products?product_search[state]=draft',
        DAWANDA_BASEURL + '/seller/products?product_search[state]=paused',
        DAWANDA_BASEURL + '/seller/products?product_search[state]=past',
        DAWANDA_BASEURL + '/seller/products?product_search[state]=active',
    ]

    iterate_urls(session, urls, parse_product_list, products)
    return products


def get_product_details(session, product_id):
    url = DAWANDA_BASEURL + '/seller/products/' + str(product_id) + '/edit'
    req = session.get(url)
    req.raise_for_status()

    product = parse_product(req.text)
    return product


def parse_ratings(text, ratings):
    req_page = BeautifulSoup(text, 'lxml')

    ratings_table = req_page.find('table', id='feedback')
    assert ratings_table is not None

    first = True
    for row in ratings_table.find_all('tr'):
        # skip the first row
        if first:
            first = False
            continue

        cells = row.find_all('td')

        rating = {
            'stars': len(cells[0].find_all('img')),
            'text': list(cells[1].stripped_strings),
            'author': cells[2].string,
            'date': cells[3].string,
        }
        ratings.append(rating)

    return [link['href'] for link in req_page.select('div.pagination > a.next_page')]


def get_ratings(session, username):
    ratings = []
    urls = [
        DAWANDA_BASEURL + '/user/feedback/' + username,
    ]

    iterate_urls(session, urls, parse_ratings, ratings)
    return ratings


def main():
    data = {}
    session = requests.Session()

    parser = argparse.ArgumentParser('Dawanda Data Extractor')
    parser.add_argument('--exit-timeout', type=int, default=5, help='wait given number of seconds before exiting (default: %(default)ds)')
    parser.add_argument('--session', help='Dawanda-Session ID to use, don\'t ask for credentials or log in at all')
    parser.add_argument('--output', '-o', default=None, help='ZIP file returning all data, defaults to "dawanda_YYYY-MM-DD_HH-MM_SS.zip"')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--skip-products', action='store_true')
    parser.add_argument('--skip-images', action='store_true')
    parser.add_argument('--skip-ratings', action='store_true')
    args = parser.parse_args()

    logging.basicConfig()
    if args.debug:
        from http import client as http_client
        http_client.HTTPConnection.debuglevel = 1

        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    if args.session is not None:
        session.cookies.set('_dawanda_session', args.session, domain='.dawanda.com', path='/')
    else:
        # we need the user to log in
        dw_user = input('DaWanda user: ')
        dw_password = getpass('DaWanda password (not shown): ')
        login_req = session.post(DAWANDA_BASEURL + '/core/sessions', data={'user[email_or_username]': dw_user, 'user[password]': dw_password, 'user[remember_me]': 'true'})
        if login_req.status_code != 201:
            print('LOGIN FAILED.', file=sys.stderr)
            sleep(args.exit_timeout)
            sys.exit(1)

    output_filename = args.output or strftime('dawanda_%Y-%m-%d_%H-%M-%S.zip')
    print('[*] output:', output_filename)
    output = ZipFile(output_filename, 'w')

    print('[*] fetching profile ... ', end='')
    profile = session.get(DAWANDA_BASEURL + '/current_user/profile').json()
    output.writestr('profile.json', json.dumps(profile, indent=2), compress_type=ZIP_DEFLATED)
    if not profile.get('logged_in', False):
        print('NOT LOGGED IN')
        output.close()
        sleep(args.exit_timeout)
        sys.exit(1)
    print(profile.get('username'))

    if not args.skip_ratings:
        print('\033[K[*] fetching ratings')
        ratings = get_ratings(session, profile['username'])
        output.writestr('ratings.json', json.dumps(ratings, indent=2), compress_type=ZIP_DEFLATED)
        print('\033[K    got', len(ratings))

    if not args.skip_products:
        print('\033[K[*] fetching products')
        products = get_product_list(session)
        output.writestr('productlist.json', json.dumps(products, indent=2), compress_type=ZIP_DEFLATED)

        idx = 0
        total = len(products)
        print('\033[K    got', total)

        for prod_id, product in products.items():
            print('\033[K    fetching details {idx}/{count}: {id}'.format(idx=idx+1, count=total, id=prod_id), end='\r', flush=True)
            details = get_product_details(session, prod_id)
            product.update(details)
            idx += 1

        output.writestr('products.json', json.dumps(products, indent=2), compress_type=ZIP_DEFLATED)

        if not args.skip_images:
            idx = 0
            total = sum(len(prod.get('product_images_attributes', [])) for prod in products.values())
            for product_id, product in products.items():
                for img in product.get('product_images_attributes', []):
                    img_id = img.get('id') or img.get('guid')
                    print('\033[K... fetching images {idx}/{count}: {prod_id} / {img_id}'.format(idx=idx+1, count=total, prod_id=product_id, img_id=img_id), end='\r', flush=True)
                    img_data = session.get(img.get('url'))
                    with output.open('product_images/' + str(img_id) + '.' + img.get('extension', 'dat').lower(), 'w') as f:
                        f.write(img_data.content)
                    idx += 1

    output.close()

    print('\033[K[+] done', end='')
    if not args.skip_products:
        print(' [', len(products), ' products]', sep='', end='')
    if not args.skip_ratings:
        print(' [', len(ratings), ' ratings]', sep='', end='')
    print()

    sleep(args.exit_timeout)


if __name__ == '__main__':
    main()
