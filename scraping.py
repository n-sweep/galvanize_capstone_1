import re
import requests
from time import sleep
from bs4 import BeautifulSoup, NavigableString
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

# Connect to MongoDB
client = MongoClient('192.168.0.209', 27017)
db = client['capstone_1']
cards_coll = db['cards']
decks_coll = db['deck_lists']
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

def get_card(name_str):
    """Returns data from Scryfall API on an individual card by name"""
    payload = {'fuzzy': '+'.join(name_str.split())}
    response = query(scryfall_api_url.format('cards/named'), payload)
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

def scrape_events(meta_url):
    """Scrape event pages using selenium"""
    events_agg = {}
    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Firefox(options=options)
    driver.get(meta_url)
    sleep(1)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    meta_dropdown = soup.find('select', {'name': 'meta'})  # get drop down selector for meta
    selected_meta = meta_dropdown.find('option', selected=True)  # get current meta
    
    def get_next(driver, class_name):
        """Check if the next button is still valid"""
        try:
            return driver.find_element_by_class_name('Nav_PN')
        except Exception as e:
            return False
    
    while True:
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
            events_agg[eid] = {
                'id': eid,
                'name': link.text,
                'date': event.find(class_='S10').text,
                'level': 4 if 'bigstar' in stars[0]['src'] else len(stars),
                'link': mtgtop8_url.format('event' + link['href']),
                'meta': selected_meta.text
            }
        
        if next_btn:
            next_btn.click()
            sleep(1)
        else:
            break

    driver.close()
    return events_agg

def scrape_top_decks(event_url):
    """Takes in a url to an event page and scrapes the top decks"""
    soup = hot_soup(event_url)
    decks_table = soup.find_all(class_='Stable')[0]
    num_players = int(re.search(r"(\d+) players -", decks_table.text).group(1))
    decks_placed = []
    for sib in decks_table.next_siblings:
        if isinstance(sib, NavigableString):
            continue
        if sib.a:
            placement, title, pilot = sib.text.split('\n')[1:-1]
            link = mtgtop8_url.format(sib.a['href'])
            deck = {
                'title': title,
                'pilot': pilot,
                'placement': placement,
                'link': link
            }
            decks_placed.append(deck)
    return decks_placed

def scrape_decklist(deck_url):
    """Takes in a deck url and returns mainboard and sideboard cards with their quantities"""
    soup = hot_soup(deck_url)
    card_re = re.compile(r"(\d+)\s(.+)")
    deck_table = soup.find_all(class_='Stable')[1]
    deck_headers = deck_table.previous_sibling.previous_sibling.find_all('td')
    archtype = deck_headers[2].text.strip('decks')
    cardlist = deck_table.table.find_all('table')
    mainboard, sideboard = [], []
    for row in cardlist.pop().find_all('span'):
        count, card = card_re.search(row.parent.text).groups()
        sideboard.append((int(count), card.strip()))

    for col in cardlist:
        for row in col.find_all('span'):
            count, card = card_re.search(row.parent.text).groups()
            mainboard.append((int(count), card.strip()))

    return {'mainboard': mainboard, 'sideboard': sideboard}


def main():
    form = 'standard'
    meta = 'History - All Worlds'
    soup = hot_soup(mtgtop8_url.format('format'), {'f': mt8_format_keys[form]})
    meta_dropdown = soup.find('select', {'name': 'meta'})  # get drop down selector for meta
    selected_meta = meta_dropdown.find('option', selected=True)  # get current meta
    metas = {opt.text: mtgtop8_url.format(opt['value']) for opt in meta_dropdown.find_all('option')}  # meta URLs
    chosen_meta = metas[meta]  # a meta url will be fed into gather_archtypes() and scrape_events()

    archtypes = gather_archtypes(chosen_meta)
    events = scrape_events(chosen_meta)

    for event in events:
        decks = scrape_top_decks(event.link)
        for deck in decks:
            decklist = scrape_decklist(deck.link)
            print(decklist)
            return


if __name__ == 'main':
    main()