from http.client import HTTPSConnection
from bs4 import BeautifulSoup
import re
import operator
import json
from multiprocessing.dummy import Pool as ThreadPool 

OUTPUT_FILE = "contrib_totals.txt"
ORG_NAME = "org_name_here"
THREADS  = 100
ACCESS_TOKEN = "https://github.com/settings/tokens"

class GitOrgContribTotals:
    def __init__(self, org, threads, access_token):
        self._pool = ThreadPool(threads) 
        self._org  = org
        self._headers = {
            "authorization":    "token {}".format(access_token),
            "user-agent":       "GitOrgContribTotals/python"
        }

    def _get_contrib_total(self,member):
        path = "/{}".format(member)
        
        #get html for member page
        host = "github.com"
        c = HTTPSConnection(host)
        c.request(
            method="GET",
            url=path,
            headers=self._headers
        )
        r = c.getresponse()

        #parse and get html element text containing contribution number
        soup = BeautifulSoup(r.read(), "html.parser")
        contrib_text = soup.find_all("h2", class_="f4 text-normal mb-2")[0].string
        
        #regex to match against the actual number 
        total = 0
        match = re.search(r'(\d*,?\d+) contributions', contrib_text)
        if match:
            total = int(match.group(1).replace(',',''))
    
        return (host + path,total)

    def _get_org_member_sublist(self, org_members, path):        
        c = HTTPSConnection("api.github.com")
        c.request(
            method="GET",
            url="/{}".format(path),
            headers=self._headers
        )
        r = c.getresponse()
        members_json = json.loads(r.read().decode('utf-8'))
        org_members.extend([member["login"] for member in members_json])
        return r.getheader("link")

    def _get_org_members(self):
        #gets all members of organisation
        org_members = []

        #get members on first page return by github api and set path for the next page
        path = "orgs/{}/members".format(self._org)
        link = self._get_org_member_sublist(org_members, path)
        if not link:
            #only one page of data
            return
        match = re.search(r'(organizations.*)>.*next', link)
        path = match.group(1)
        while True:
            #keep updating the path for each page
            link = self._get_org_member_sublist(org_members, path)
            match = re.search(r'prev.*?(organizations.*?)>;.*next', link)
            if match:
                path = match.group(1)
            else:
                #all pages processed
                break
        return org_members

    def get_totals(self):
        org_members = self._get_org_members()
        results = {}

        if org_members:
            #threaded call to get total for each organisation member
            results = self._pool.map(self._get_contrib_total, org_members)
            #sort in descending order
            results = sorted(results, key=operator.itemgetter(1), reverse=True)
        else:
            print("No organisation members were found...")

        return results

if __name__ == "__main__":
    contribs = GitOrgContribTotals(ORG_NAME, THREADS, ACCESS_TOKEN).get_totals()
    #write result to file
    with open(OUTPUT_FILE, "w") as f:
        for url,total in contribs:
            f.write("{} :\t\t{}\n".format(url, total))

