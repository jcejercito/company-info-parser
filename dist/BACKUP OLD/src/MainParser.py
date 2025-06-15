from bs4 import BeautifulSoup
from bs4 import SoupStrainer
from urllib.parse import urljoin
import httpx
import asyncio
from aiolimiter import AsyncLimiter
import numpy as np
import pandas as pd
import openpyxl
import json
import os.path
import time

def visitCountry(url):
    print("Collecting URLs... (this may take a while)")
    regions_container = SoupStrainer(class_="nav nav-stacked") #div element of that contains the links of country regions
    regionsPage = httpx.get(url) #Parse the html of the url

    countryDoc = BeautifulSoup(regionsPage.text, 'html.parser', parse_only=regions_container) #Gets the regions container (div) of the country

    regions = countryDoc.find_all("a", href=True) #Retrieve each of the links of the regions
    visitRegion(regions)

def visitRegion(regions):
    for a in regions:
        setCurrentRegion(a.text.strip())
        print("======Parsing region " + currentRegion + "======")

        regionURL = urljoin(country, a['href']) #Joins the current url and the href to make an absolute URL
        region = httpx.get(regionURL, timeout=timeout) #navigate to the specific region

        while True:            
            try:
                citiesOuterContainer = SoupStrainer(class_='tab-pane active') #main container of the city links
                citiesContainerDoc = BeautifulSoup(region.text, 'html.parser', parse_only=citiesOuterContainer) #Retrieve container of the cities
                
                citiesInnerContainerDoc = citiesContainerDoc.find(class_='row') #Get the inner container of the links 

                cities = citiesInnerContainerDoc.find_all("a", href=True) #Retrieve each of the links of the cities
                
                asyncio.run(visitCities(cities))

                nextButton = citiesContainerDoc.find(rel='next') #Find the next pagination button
                nextURL = urljoin(country, nextButton['href'])

                region = httpx.get(nextURL, timeout=timeout) #go to the next page (if there is any)
            except TypeError:
                break #Go to the next region when the next button does not exist anymore
            except AttributeError:
                #special case for berlin, because its a city already
                visitRegionCity(region)
                break
            except (ConnectionResetError, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError):
                print("Connection reset. Restarting the region...")
                continue #When the connection is reset, just restart the connection

async def visitCities(cities):
    rateLimit = AsyncLimiter(100) #set number of requests so that we don't overload the website
    async with httpx.AsyncClient() as client:
        tasks = []
        for city in cities:
            tasks.append(visitCity(client, city, rateLimit)) #add "visitCity" to the list of tasks needed to be done
        await asyncio.gather(*tasks, return_exceptions=True)

async def visitCity(client, city, limiter):    
    path = 'savedlinks/[' + currentRegion + "] " + city.text + '.json'
    fromExcept = 0 #marker to show if we came from an except call

    #IF THE CITY IS SHOWN IN CACHE, SKIP THE CITY
    if(os.path.isfile(path)):
        print("Found stored links for city " + city.text + ". Skipping...")
        return

    async with limiter:
        while True:
            try:
                print("Parsing city " + city.text) #For debugging purposes

                if(fromExcept == 0):
                    cityURL = urljoin(country, city['href']) #Joins the current url and the href to make an absolute URL
                    citySite = await client.get(cityURL, timeout=timeout) #navigate to the specific city
                while True:
                    try:
                        companiesContainer = SoupStrainer(class_='list-group') #list of the companies
                        companiesDoc = BeautifulSoup(citySite.text, 'html.parser', parse_only=companiesContainer) #Retrieve each of the links of the cities
                        
                        companies = companiesDoc.find_all("a", href=True) #Retrieve each of the links of the cities
                        
                        storeCompanyURL(companies)
                        
                        paginationContainer = SoupStrainer(class_='pagination') #get only the pagination div
                        paginationDoc = BeautifulSoup(citySite.text, 'html.parser', parse_only=paginationContainer) #get the html of the pagination

                        nextButton = paginationDoc.find(rel='next') #Find the next pagination button
                        nextURL = urljoin(country, nextButton['href'])
                        print(nextURL)
                        citySite = await client.get(nextURL, timeout=timeout) #go to the next page (if there is any)

                    except TypeError:
                        break #Go to the next region when the next button does not exist anymore

            except (ConnectionResetError, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError):
                print("Connection reset. Retrying...")
                fromExcept = 1 #set marker to continue where we came from
                continue #When the connection is reset, just restart the connection
            
            else:
                break
    
    #store the cities in cache
    companyURLCache = {currentRegion : companyURLs}
    
    #store the cache in JSON file
    storeToCache(currentRegion, companyURLCache)

    companyURLs.clear() #empty the list
    print("Links of " + currentRegion + " stored in savedlinks folder")

def visitRegionCity(city):    
    path = 'savedlinks/[' + currentRegion + "] " + currentRegion + '.json'

    #IF THE CITY IS SHOWN IN CACHE, SKIP THE CITY
    if(os.path.isfile(path)):
        print("Found stored links for city " + currentRegion + ". Skipping...")
        return

    while True:
        try:
            companiesContainer = SoupStrainer(class_='list-group') #list of the companies
            companiesDoc = BeautifulSoup(city.text, 'html.parser', parse_only=companiesContainer) #Retrieve each of the links of the cities
            
            companies = companiesDoc.find_all("a", href=True) #Retrieve each of the links of the cities
            
            storeCompanyURL(companies)
            
            paginationContainer = SoupStrainer(class_='pagination') #get only the pagination div
            paginationDoc = BeautifulSoup(city.text, 'html.parser', parse_only=paginationContainer) #get the html of the pagination

            nextButton = paginationDoc.find(rel='next') #Find the next pagination button
            nextURL = urljoin(country, nextButton['href'])
            print(nextURL)
            city = httpx.get(nextURL) #go to the next page (if there is any)

        except TypeError:
            break #Go to the next region when the next button does not exist anymore
        except (ConnectionResetError, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError):
                print("Connection reset. Retrying...")
                continue #When the connection is reset, just restart the connection
    
    #store the cities in cache
    companyURLCache = {city.text : companyURLs}
    
    #store the cache in JSON file
    storeToCache(city.text, companyURLCache)

    companyURLs.clear() #empty the list
    print("Links of " + city.text + " stored in savedlinks folder")

def storeToCache(city, companyURLCache):
    with open('savedlinks/[' + currentRegion + "] " + city + '.json', "w") as outfile: 
        json.dump(companyURLCache, outfile)

def storeCompanyURL(companies):
    for company in companies:
            companyURL = urljoin(country, company['href'])
            companyURLs.append(companyURL)

async def getCompaniesData(companyURLs):
    rateLimit = AsyncLimiter(100) #set number of requests so that we don't overload the website

    async with httpx.AsyncClient() as client:
        tasks = []
        for companyURL in companyURLs:
            tasks.append(getCompanyData(client, companyURL, rateLimit)) #add "visitCity" to the list of tasks needed to be done
        await asyncio.gather(*tasks, return_exceptions=True)

async def getCompanyData(client, companyURL, limiter):
    async with limiter:
        while True:
            try:
                print("Taking company data: " + companyURL)
                companyPage = await client.get(companyURL) #Parse the html of the url
                
                detailsContainer = SoupStrainer(class_="adressbox") #div element of that contains the info of company
                countryDoc = BeautifulSoup(companyPage.text, 'html.parser', parse_only=detailsContainer) #Gets the regions container (div) of the info

                #Retrieving the information
                companyName = countryDoc.find(itemprop='name').text
                streetAddress = countryDoc.find(itemprop='streetAddress').text
                postalCode = countryDoc.find(itemprop='postalCode').text
                addressLocality = countryDoc.find(itemprop='addressLocality').text
                
                try:
                    telephone = countryDoc.find(itemprop='telephone').text
                except:
                    telephone = 'None'

                try:
                    fax = countryDoc.find(itemprop='faxNumber').text
                except:
                    fax = 'None'

                try:
                    emailwebsite = countryDoc.find_all('a') #get the email and website

                    if(len(emailwebsite) != 1):
                        email = emailwebsite[0].text
                        website = emailwebsite[1].text
                    else:
                        email = 'None'
                        website = 'None'

                except:
                    emailwebsite = 'none'

                address = (companyName + " " + streetAddress + " " + postalCode + " " + addressLocality)

                postCompanyData(companyName, address, telephone, fax, email, website) #after gathering, append them to the dictionary
            
            except(ConnectionResetError, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError):
                print("Connection reset. Retrying...")
                continue #When the connection is reset, just restart the connection
            
            else:
                break

def postCompanyData(companyName, address, telephone, fax, email, website):
    companyData['Company Name'].append(companyName)
    companyData['Address'].append(address)
    companyData['Telephone'].append(telephone)
    companyData['Fax'].append(fax)
    companyData['Email'].append(email)
    companyData['Website'].append(website)

def setCurrentRegion(region):
    global currentRegion
    currentRegion = region

try:
    start_time = time.perf_counter()

    timeout = httpx.Timeout(None) #fine-tuning timeouts

    countries = ['http://www.firmendb.de/deutschland/index.php', 'http://www.firmendb.de/oesterreich/index.php', 'http://www.firmendb.de/schweiz/index.php']
    companyURLs = []
    companyURLCache = dict()

    companyData = {
        'Company Name': [],
        'Address': [],
        'Telephone': [],
        'Fax': [],
        'Email': [],
        'Website': []
    }

    for country in countries:
        visitCountry(country)

    #Parse each json file and get the company
    directory = 'savedlinks' #folder where json files are

    #Iterate through the files in the directory
    for filename in os.scandir(directory):
        f = open(filename.path)

        data = json.load(f)
        
        #get the name of the city through the filename
        city = filename.name.replace('.', ' ').split(" ")
        city = city[1]

        urls = data[city]

        asyncio.run(getCompaniesData(urls))

    companyDF = pd.DataFrame(companyData) #Create a dataframe based on the python dict
    companyDF.to_excel('CompanyInfo.xlsx') #Move all of these into the excel file

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time

    print('Done after ' + str(elapsed_time) + 's!')
except Exception as e:
    print(e, file='crash log.txt')