# **The Original Trading Card Game**

Concieved and developed by mathematician Richard Garfield, **Magic: the Gathering** (commonly known as *MTG* or simply *Magic*) is a trading card game released by Washington State-based game publisher Wizards of the Coast (WotC). The game was debuted at a GenCon gaming convention on August 5, 1993 and by the end of October 1993, WotC had sold out of their initial run of 10 million cards. By the end of 1994, Magic: the Gathering had sold over 1 billion cards.

Not only does *MTG* still enjoy popularity - and regularly released sets of new cards - to this day, but it was the first of its kind, paving the way for other successful titles such as *Yu-Gi-Oh* and the *Pokémon Trading Card Game*, and many more that have come and gone over the years. <br/><br/>

![a large Magic: the Gathering tournament](images/mtgtourny.jpg)
<br/><br/>

## **Background & Motivation**

![the MTG 'color pie'](images/MM20161114_Wheel_small.png)

*Magic* became a part of my life at a young age and it wasn't long before I was playing competitvely in sanctioned events. First at local collectables stores and later traveling to larger events, often in neighboring states, which I continued to do for over a decade. It has been some years since I played in this context, but over the years I met many other players who remain close friends to this day, and the game remains very close to my heart.

*Magic* is a game of both skill and chance, where decisions made by a player can have consequences many turns on. Each player has their own deck to draw from, and the decks are not (necessarily) identical, but built by the individual player from a larger pool of available cards. After over 25 years of printing, there are tens of thousands of cards to choose from.
<br/><br/>

### **Rarity as an Attribute**

Being a trading card game, a big part of *MTG* is collectability and, naturally, a big part of collectability is the scarcity or rarity of a collectible item. *Magic* cards are printed with a predetermined rarity set by Wizards of the Coast. This is somewhat an indication of how 'powerful' or how effective a card would be in a competitive setting. More concretely, it's an indication of how many of that card was manufactured, as fewer copies of a rare card are printed than those of a common card.

**So, rare cards should be better cards. Does a higher ratio of rare cards in your deck really translate to wins?**
<br/><br/>

# **Data & Analysis**

Using a combination of the Requests, Selenium and BeautifulSoup Python libraries, I scraped the top performing decks from tournament results at [mtgtop8.com](https://www.mtgtop8.com) and individual card stats from [magicthegathering.oi](https://magicthegathering.io)'s convenient API, storing the data with MongoDB

![Ratio of Rare Cards in Winning Decks](images/1st_vs_all.png)

Visually, the 1st place decks tend to have a few more rare cards, but the difference was not statistically significant. After testing each group against one another using a Welch's T-test, I found that the p-values for each test were more than double the established alpha of 0.05, even before applying the Bonferroni correction, leaving us to fail to reject the null hypothesis that 
<br/><br/>

# Conclusions & Next Steps

While card choices and deck construction are important, it's players that ultimately win games. For this project, results considered were taken from Worlds tournaments between 1994 and 2019 - the highest level of competition in the game. At this level, everyone has access to the good cards they need and it's game choices that decide matches. Given this, it's not surprising to find that ratios of rare cards don't have a connection to games won.

I would be interesting to consider in the future lower level games, which are also much more common than the annual Worlds event. Players at this level are less experienced and may have less access to more effective cards, leading to decks with more of them winning more often.
<br/><br/>

## Technologies Used to Complete this Project
![Tech Stack](images/stack.png)