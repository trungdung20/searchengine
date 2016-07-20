import urllib2
from bs4 import *
import re
from urlparse import urljoin
from pysqlite2 import dbapi2 as sqlite
import nn
import sys

#create a list of words to ignore
ignorewords = set(['the', 'of', 'to', 'and', 'a', 'in', 'is', 'it'])
class crawler:
    #Initialize the crawler with the name of database \
    def __init__(self, dbname):
        self.con = sqlite.connect(dbname)

    def __del__(self):
        self.con.close()

    def dbcommit(self):
        self.con.commit()

    #auxilliary function for getting an entry id and adding
    #it if it;s not present
    def getentryid(self, table, field, value, createnew = True):
        cur = self.con.execute(
        "select rowid from %s where %s = '%s'" %(table, field, value))
        res = cur.fetchone()
        if res == None:
            cur = self.con.execute(
            "insert into %s (%s) values ('%s')" %(table, field, value)
            )
            return cur.lastrowid
        else:
            return res[0]

    #Index an individual page
    def addtoindex(self, url, soup):
        if self.isindexed(url): return
        print 'Indexing ' + url

        #Get the individual words
        text = self.gettextonly(soup)
        words = self.separatewords(text)

        #Get the URL id
        urlid = self.getentryid('urllist', 'url', url)

        #Link each word to this url
        for i in range(len(words)):
            word = words[i]
            if word in ignorewords: continue
            wordid = self.getentryid('wordlist','word', word)
            self.con.execute("insert into wordlocation(urlid, wordid, location) \
                values (%d,%d,%d)" % (urlid, wordid,i))

    #Extract the text from an HTML page (no tags)
    def gettextonly(self, soup):
        v= soup.string
        if v == None:
            c = soup.contents
            resulttext = ''
            for t in c:
                subtext = self.gettextonly(t)
                resulttext += subtext + '\n'
            return resulttext
        else:
            return v.strip()

    #Seperate the words by any non-whitespace character
    def separatewords(self, text):
        splitter = re.compile('\\W*')
        return [s.lower() for s in splitter.split(text) if s!= '']

    #Return true of this url is already indexed
    def isindexed(self, url):
        u = self.con.execute(
            "select rowid from urllist where url='%s'" %url
        ).fetchone()

        if u != None:
                #Check if it has actually been crawled
            v = self.con.execute(
                'select * from wordlocation where urlid=%d' %u[0]
            ).fetchone()
            if v != None: return True
        return False
    #def add link words
    def addlinkword(self, linkid , linkText):
        words = self.separatewords(linkText)
        #link each word to url
        for word in words:
            wordid = self.getentryid('wordlist','word', word)
            cur = self.con.execute("select * from linkwords where wordid='%s'" %wordid).fetchone()
            if cur == None:
                print "######################################################"
                print "add word with context %s and link %s to linkword index"%(word,linkid)
                self.con.execute("insert into linkwords(wordid, linkid) values(%d, %d)" %(wordid, linkid))


    #Add a link between two pages
    def addlinkref(self, urlFrom, urlTo, linkText):
        urlFromid = self.getentryid('urllist', 'url', urlFrom)
        urlToid = self.getentryid('urllist', 'url', urlTo)

        if urlFromid != None and urlToid != None:
            check_link_text = self.con.execute("select rowid from linkwords where linkid='%s'"%urlToid).fetchone()
            #print check_link_text
            if check_link_text == None:
                self.addlinkword(urlToid, linkText)
            print "#####################################################"
            print "add url %s to url %s with content %s" %(urlToid, urlFromid, linkText)
            self.con.execute("insert into link(fromid, toid) \
                        values (%d, %d)" %(urlFromid, urlToid))

    #Starting with a list of pages, do a breadth
    #first search to the given depth, indexing pages
    #as we go
    def crawl(self, pages, depth=2):
        for i in range(depth):
            newpages = set()
            for page in pages:
                try:
                    c = urllib2.urlopen(page)
                except:
                    print "Could not open %s" %page
                    continue
                soup = BeautifulSoup(c.read())
                self.addtoindex(page, soup)

                links = soup('a')
                for link in links:
                    if ('href' in dict(link.attrs)):
                        url = urljoin(page, link['href'])
                        if url.find("'") != -1: continue
                        url = url.split("#")[0]
                        if url[0:4] == 'http' and not self.isindexed(url):
                            newpages.add(url)
                        linkText = self.gettextonly(link)
                        #print "add page %s to url %s" %(page, url)
                        self.addlinkref(page, url, linkText)
                self.dbcommit()
            pages = newpages

    def calculatepagerank(self, iterations = 20):
        #clear out the current PageRanks tables
        self.con.execute('drop table if exists pagerank')
        self.con.execute('create table pagerank(urlid primary key, score)')

        #initialize every url with a PageRank of 1
        self.con.execute('insert into pagerank select rowid, 1.0 from urllist')
        self.dbcommit()

        for i in range(iterations):
            print "iterations %d" %(i)
            for (urlid,) in self.con.execute('select rowid from urllist'):
                pr = 0.15
                #Loop through all the pages that link to this one
                for (linker, ) in self.con.execute(
                'select distinct fromid from link where toid=%d' % urlid):
                    #get the pagerank of the linker
                    linkingpr = self.con.execute(
                    'select score from pagerank where urlid=%d' % linker).fetchone()[0]

                    #get the total number of links from the linker
                    linkingcount = self.con.execute(
                    'select count(*) from link where fromid=%d' % linker
                    ).fetchone()[0]
                    pr += 0.8*(linkingpr/linkingcount)
                print "#####################################################\n"
                print "update link with id = %d with pagerank score of = %d \n"%(urlid, pr)
                self.con.execute(
                'update pagerank set score = %f where urlid = %d' %(pr, urlid)
                )
            self.dbcommit()
    #create the datavase tables
    def createindextables(self):
        self.con.execute('create table urllist(url)')
        self.con.execute('create table wordlist(word)')
        self.con.execute('create table wordlocation(urlid, wordid, location)')
        self.con.execute('create table link(fromid integer, toid integer)')
        self.con.execute('create table linkwords(wordid, linkid)')
        self.con.execute('create index wordidx on wordlist(word)')
        self.con.execute('create index urlidx on urllist(url)')
        self.con.execute('create index wordurlidx on wordlocation(wordid)')
        self.con.execute('create index urltoidx on link(toid)')
        self.con.execute('create index urlfromidx on link(fromid)')
        self.dbcommit()

class searcher:
    def __init__(self, dbname):
        self.con = sqlite.connect(dbname)

    def __del__(self):
        self.con.close()

    def getmatchrows(self, q):
        #Strings to build the query
        fieldlist = 'w0.urlid'
        tablelist = ''
        clauselist = ''
        wordids = []

        #PLIT THE WORDS BY SPACES
        words = q.split(' ')
        tablenumber = 0
        can_execute = False
        for word in words:
            #print word
            #Get the word ID
            wordrow = self.con.execute(
            "select rowid from wordlist where word ='%s'"%word
            ).fetchone()
            #print wordrow
            if wordrow != None:
                can_execute = True
                wordid = wordrow[0]
                wordids.append(wordid)
                if tablenumber > 0:
                    tablelist += ','
                    clauselist += ' and '
                    clauselist += 'w%d.urlid=w%d.urlid and '%(tablenumber -1, tablenumber)
                fieldlist += ',w%d.location' % tablenumber
                tablelist += 'wordlocation w%d' %tablenumber
                clauselist += 'w%d.wordid=%d' %(tablenumber, wordid)
                tablenumber += 1

        #create the query from the seperate parts
        if can_execute:
            fullquery = 'select %s from %s where %s'%(fieldlist, tablelist, clauselist)
            #print fullquery
            cur = self.con.execute(fullquery)
            rows = [row for row in cur]
            return rows, wordids
        else:
            return None;

    def getscoredlist(self, rows, wordids):
        totalscores = dict([(row[0], 0) for row in rows])

        #This is where you'll later oyt the scouring functions
        weights = [(1, self.neural_network(rows, wordids)),
                    (1.0, self.frequencyscore(rows))]
        for (weight, score) in weights:
            for url in totalscores:
                totalscores[url] += weight * score[url]
        return totalscores

    def geturlname(self, id):
        return self.con.execute(
        "select url from urllist where rowid=%d" %id
        ).fetchone()[0]

    def query(self, q, result_only=0):
        try:
            rows, wordids = self.getmatchrows(q)
            scores = self.getscoredlist(rows, wordids)
            rankedscores = sorted([(score, url) for (url, score) in scores.items()], reverse = 1)
            if result_only == 0 :
                for (score, urlid) in rankedscores[0:10]:
                    print '%f\t%s' %(score, self.geturlname(urlid))
            if result_only == 1:
                return rankedscores, wordids
        except Exception as e:
            print("Oops! Cannot find result")

    def normalizescores(self, scores, smallIsBetter = 0):
        vsmall = 0.00001 #Avoid division by zero errors
        if smallIsBetter:
            minscore = min(scores.values())
            if minscore == 0:
                minscore = 1
            return dict([(u,float(minscore)/max(vsmall,l)) for (u, l) \
                        in scores.items()])
        else:
            maxscore = max(scores.values())
            if maxscore == 0:
                maxscore = 1
            if maxscore == 0: maxscore = vsmall
            return dict([(u, float(c)/maxscore) for (u,c) in scores.items()])

    def frequencyscore(self, rows):
        counts = dict([(row[0], 0) for row in rows])
        for row in rows: counts[row[0]] += 1
        return self.normalizescores(counts)

    def rankscore(self, rows):
        page_ranks = dict([(row[0],0) for row in rows])
        for row in rows:
            score = self.con.execute("select score from pagerank where urlid=%d"%row[0]).fetchone()[0]
            page_ranks[row[0]] += score
        return self.normalizescores(page_ranks)

    def locationscore(self, rows):
        locations = dict([(row[0], 1000000) for row in rows])
        for row in rows:
            loc = sum(row[1:])
            if loc < locations[row[0]]:locations[row[0]] = loc

        return self.normalizescores(locations, smallIsBetter = 1)

    def distancescore(self, rows):
        #If there;s only one word, everyone wins
        if len(rows[0]) <= 2: return dict([(row[0],1.0) for row in rows])

        #Initialize the dictionary with large values
        mindistance = dict([(row[0], 1000000) for row in rows])

        for row in rows:
            dist = sum([abs(row[i] - row[i-1]) for i in range(2, len(row))])
            if dist < mindistance[row[0]]: mindistance[row[0]] = dist

        return self.normalizescores(mindistance, smallIsBetter = 1)

    def inboundlinkscore(self, rows):
        uniqueurls = set([row[0] for row in rows])
        inboundcount = dict([(u, self.con.execute( \
                        'select count(*) from link where toid=%d' % u).fetchone()[0]) \
                        for u in uniqueurls])
        return self.normalizescores(inboundcount)

    def linktextscore(self, rows, wordids):
        linkscores = dict([(row[0], 0) for row in rows])
        for wordid in wordids:
            cur = self.con.execute('select link.fromid, link.toid from linkwords, link \
                                    where linkwords.wordid=%d and linkwords.linkid=link.toid' % wordid)
            for (fromid, toid) in cur:
                if toid in linkscores:
                    pr = self.con.execute('select score from pagerank where urlid=%d' % fromid).fetchone()[0]
                    linkscores[toid] += pr
        maxscore = max(linkscores.values())
        if maxscore == 0:
            maxscore = 1
        normalizescores = dict([(u, float(l)/maxscore) for (u, l) in linkscores.items()])
        return normalizescores

    def neural_network(self, rows, wordids):
        urlids = [urlid for urlid in set([row[0] for row in rows])]
        network_nel = nn.searchnet('nn.db')
        node_output = network_nel.getresult(wordids, urlids)
        net_score = dict([(urlids[i], node_output[i]) for i in range(len(urlids))])
        return self.normalizescores(net_score)

def trainnetwork(query, search_class, net_class, target, iterations):
    for q in query:
        try:
            rows_q, wordids_q = search_class.query(q,1)
            urlids_q = [urlid for urlid in set([row_q[1] for row_q in rows_q])]
            print "train network begin for %s with %s id and %d url targets " %(q, wordids_q, urlids_q[target])
            for i in range(iterations):
                print "****************************************************"
                print "train through %s iterations" %i
                net_class.trainquery(wordids_q, urlids_q, urlids_q[target])
                if i == iterations-1:
                    print "finish training %s" %q
        except Exception as e:
            print "Exit trainning process, bye"


def testnetwork(query,search_class, net_class):
    try:
        rows_q, wordids_q = search_class.query(query, 1)
        urlids_q = [urlid for urlid in set([row_q[1] for row_q in rows_q])]
        print net_class.getresult(wordids_q, urlids_q)
    except Exception as e:
        print "Exit testing process due to unable to find matched query"


if __name__ == '__main__':
    import searchengine
    import nn
    from sys import argv

    #scraw = searchengine.crawler('searchindex.db')
    #scraw.calculatepagerank()
    #print "######################################"
    #print "generate page rank score"
    search = searchengine.searcher('searchindex.db')
    mynet = nn.searchnet('nn.db')

    #mynet.maketables()
    query = []

    if argv[1] == 'train':
        for element in sys.argv[2:]:
            query.append(element)
        trainnetwork(query, search, mynet, 5, 1000)
    if argv[1] == 'test':
        testnetwork('female',search, mynet)
    if argv[1] == 'search':
        print "************************************"
        print "test result for %s" %argv[2]
        search.query(argv[2], 0)
