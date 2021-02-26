import re
import requests
import numpy as np
import pandas as pd
from pprint import pprint
from time import sleep
from bs4 import BeautifulSoup, NavigableString
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

# Connect to MongoDB
client = MongoClient('mongodb://192.168.0.209', 27017)
db = client['capstone_1']
cards_coll = db['cards']
decks_coll = db['decks']
decklists_coll = db['deck_lists']
events_coll = db['events']

# Base URLs for building requests
scryfall_api_url = 'https://api.scryfall.com/{}'  # API docs: https://scryfall.com/docs/api
mtgtop8_url = 'https://www.mtgtop8.com/{}'

# mtgtop8.com format keys for building requests
mt8_format_keys = {
    'vintage': 'VI',
    'legacy': 'LE',
    'modern': 'MO',
    'pioneer': 'PI',
    'historic': 'HI',
    'standard': 'ST',
    'commander': 'EDH',
    'limited': 'LI',
    'pauper': 'PAU',
    'peasant': 'PEA',
    'block': 'BL',
    'extended': 'EX',
    'highlander': 'HIGH',
    'canadian_highlander': 'CHL'
}

def query(link, payload={}):
    """A requests wrapper function"""
    response = requests.get(link, params=payload)
    if response.status_code != 200:
        print('WARNING', response.status_code)
        print(response.content)
    return response

def get_card(name_str, page=1):
    """Returns data from magicthegathering.io API on an individual card by name"""
    payload = {'name': name_str, 'page': page}
    response = query('https://api.magicthegathering.io/v1/cards', payload)
    return response.json()

def hot_soup(url, payload={}):
    """Makes a steaming bowl of hot soup"""
    response = query(url, payload)
    soup = BeautifulSoup(response.content, 'html.parser')
    return soup

def gather_archtypes(meta_url):
    """Gathering a list of archtypes among deck strategies for a meta"""
    soup = hot_soup(meta_url)
    archtypes = { strat: [] for strat in ['aggro', 'control', 'combo'] }
    for strat in soup.find_all(class_='Stable')[0].find_all(rowspan=True):  # In this table, only the style type headers use 'rowspan'
        strat_str = strat.contents[0].lower()  # Get corrosponding key for archtypes dict
        item = strat.parent

        # Gather each archtype under each strategy type
        while len(archtypes[strat_str]) < int(strat['rowspan']) - 1:  # Rowspan == number of archtypes under this style
            item = item.next_sibling
            if isinstance(item, NavigableString):
                continue
            if item.a:  # If this sibling has a link, we know it's what we're looking for
                text  = item.a.text
                num_decks = int(item.contents[3].text)
                archtypes[strat_str].append((text, num_decks))
    
    return archtypes

def scrape_events(meta_url, collection):
    """Scrape event pages using selenium"""
    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Firefox(options=options)
    driver.get(meta_url)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    meta_dropdown = soup.find('select', {'name': 'meta'})  # get drop down selector for meta
    selected_meta = meta_dropdown.find('option', selected=True)  # get current meta
    
    def get_next(d, class_name):
        """Check if the next button is still valid"""
        try:
            button = d.find_elements_by_class_name('Nav_PN')[-1]
            return button if button.text == 'Next' else False
        except Exception as e:
            return False
    
    page = 1
    while True:
        print(f'\nScraping event page {page}...')
        next_btn = get_next(driver, 'Nav_PN')
        soup = BeautifulSoup(driver.page_source, 'html.parser')  # make some soup
        
        for event in soup.find_all(class_='Stable')[2].find_all(class_='hover_tr'):  # 10 events list table
            """
                This loop iterates through event table rows, pulling out an ID number,
                the star rating and the date of the event
            """
            link = event.a  # associated hyperlink
            eid = re.search(r"e=(\d+)&", link['href']).group(1)  # unique id number
            stars = event.find(class_='O16').find_all('img')  # star rating / level
            collection.insert_one({
                'id': eid,
                'name': link.text,
                'date': event.find(class_='S10').text,
                'level': 4 if 'bigstar' in stars[0]['src'] else len(stars),
                'link': mtgtop8_url.format(link['href']),
                'meta': selected_meta.text
            })
            
        if next_btn:
            next_btn.click()
            page += 1
            sleep(1)
        else:
            print('\n\n')
            driver.close()
            break

def scrape_top_decks(event_url, event_id, archtypes, collection):
    """Takes in a url to an event page and scrapes the top decks"""
    soup = hot_soup(event_url)
    top8_list = soup.find('div', {'id': 'top8_list'})
    decks_table = top8_list.contents[0] if top8_list else soup.find_all(class_='Stable')[0]
    # num_players = int(re.search(r"(\d+) players -", decks_table.text).group(1))  This fails sometimes but I haven't found the culprit
    for sib in decks_table.next_siblings:
        if isinstance(sib, NavigableString):
            continue
        if sib.a:
            href = sib.a['href']
            did = re.search(r"d=(\d+)&", href).group(1)  # unique id number
            link = mtgtop8_url.format('event' + href)
            
            # Check if this deck already exists - I was getting duplicate values for some reason, but a surprisingly small number of them.
            if collection.count_documents({'id': did}, limit=1) > 0:
                print(f'Duplicate found: {link}')
            
            mainboard, sideboard, archtype = scrape_decklist(link)
            placement, title, pilot = sib.text.split('\n')[1:-1]
            deck = {
                'id': did,
                'event_id': event_id,
                'title': title,
                'pilot': pilot,
                'archtype': archtype,
                'placement': placement,
                'mainboard': mainboard,
                'sideboard': sideboard,
                'link': link
            }
            for strat, arches in archtypes.items():
                if archtype in [arch[0] for arch in arches]:
                    deck['strategy'] = strat
            collection.insert_one(deck)
            print(f"  - {deck['title']} by {deck['pilot']} scraped.")

def scrape_decklist(deck_url):
    """Takes in a deck url and returns mainboard and sideboard cards with their quantities"""
    soup = hot_soup(deck_url)
    card_re = re.compile(r"(\d+)\s(.+)")
    deck_table = soup.find_all(class_='Stable')[1]
    deck_headers = deck_table.previous_sibling.previous_sibling.find_all('td')
    archtype = deck_headers[2].text.replace('decks', '')
    cardlist = deck_table.table.find_all('table')
    mainboard, sideboard = [], []
    for row in cardlist.pop().find_all('span'):
        count, card = card_re.search(row.parent.text).groups()
        sideboard.append((int(count), card.strip()))

    for col in cardlist:
        for row in col.find_all('span'):
            count, card = card_re.search(row.parent.text).groups()
            mainboard.append((int(count), card.strip()))

    return mainboard, sideboard, archtype

def scrape_metas(form):
    """Scrapes all potential metas from a format page"""
    soup = hot_soup(mtgtop8_url.format('format'), {'f': mt8_format_keys[form]})
    meta_dropdown = soup.find('select', {'name': 'meta'})  # get drop down selector for meta
    metas = {opt.text: mtgtop8_url.format(opt['value']) for opt in meta_dropdown.find_all('option')}  # meta URLs
    return metas

def initial_scrape():  # First scrape of events and winning decklists
    form = 'standard'
    meta = 'History - All Worlds'
    metas = scrape_metas(form)
    chosen_meta = metas[meta]  # a meta url will be fed into gather_archtypes() and scrape_events()

    archtypes = gather_archtypes(chosen_meta)
    print(f'Scraping meta [{meta}]...')
    events = scrape_events(chosen_meta, events_coll)
    
    for event in events_coll.find():
        print(f"Scraping decks from event {event['name']}...")
        scrape_top_decks(event['link'], event['id'], archtypes, decks_coll)
        print('\n')

def placement_fix():
    """Regrouping placement records for easier catigoration"""
    def func(place):
        if place in ['3', '4']:
            return '3-4'
        elif place in ['5', '6', '7', '8']:
            return '5-8'
        else:
            return place
        
    for place in decks_coll.find({}):
        record_id = place['_id']
        decks_coll.update_one({'_id': record_id}, {'$set': {'placement': func(place['placement'])}})

def build_decklists(df):
    """takes in our merged events dataframe and fills Decklist database"""
    for index, row in df[['mainboard', 'sideboard']].iterrows():
        for i, vals in enumerate(row):
            for qty, card in vals:
                decklists_coll.insert_one({
                    'deck_id': index,
                    'name': card,
                    'quantity': qty,
                    'board': row.index[i]
                })

def scrape_cards(cards_list):
    i = 1
    for name in cards_list:
        cards_coll.insert_one(get_card(name)['cards'][0])
        if i % 10 == 0:
            print(f'{i} cards gathered.')
        i += 1
        sleep(1)

def main():
    strat_fix = {
        'Eldrazi Green': 'aggro',
        'Mannequin': 'control',
        'Elves!': 'aggro'}

    remove_keys = [
        'set',
        'setName',
        'artist',
        'number',
        'multiverseid',
        'imageUrl',
        'rulings',
        'foreignNames',
        'printings',
        'originalText',
        'originalType',
        'legalities',
        'variations',
        'watermark']

    deck_df = pd.DataFrame(list(decks_coll.find({}, {'_id':0, 'link':0})))
    event_df = pd.DataFrame(list(events_coll.find({}, {'_id':0, 'link':0})))
    merged = event_df.merge(deck_df, left_on='id', right_on='event_id')
    convert = {s: int for s in ['id_y', 'event_id']}
    merged = merged.astype(convert)
    merged.set_index('id_y', inplace=True)
    merged.rename_axis('id', inplace=True)
    merged.drop('id_x', axis=1, inplace=True)
    merged.drop([253183, 253184, 108514], axis=0, inplace=True)

    for rid in [207945, 108523, 108521, 108516]:
        title = merged.loc[207945]['title']
        merged.at[rid, 'strategy'] = strat_fix[title]
        merged.at[rid, 'archtype'] = title
    
    decklist_df = pd.DataFrame(list(decklists_coll.find({}, {'_id':0, 'link':0})))
    cards_data = list(cards_coll.find({}, {'_id': 0}))

    cards_df = pd.DataFrame(cards_data)
    cards_df.drop(remove_keys, axis=1, inplace=True)
    cards_df.set_index('name', inplace=True)

    unique_cards = decklist_df['name'].unique()
    missing = np.setdiff1d(unique_cards, np.array(cards_df.index))

    def ask(response):
        for i, card in enumerate(response['cards']):
            print('\t', i, card['name'], f"({card['names']})" if 'names' in card else '')
        return input('Choose a number or "next" or "skip"')

    for name in missing:
        page = 1
        print('\n')
        print(name)
        response = get_card(name.split('/')[0].strip())
        correct_index = ask(response)
        if correct_index == 'skip':
            sleep(1)
            continue
        while correct_index == 'next':
            page += 1
            response = get_card(name.split('/')[0].strip(), page)
            correct_index = ask(response)
        cards_coll.insert_one(response['cards'][int(correct_index)])
        sleep(1)

if __name__  == '__main__':
    main()
