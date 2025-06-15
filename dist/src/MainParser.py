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
import logging
import traceback

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

        global regionURL
        regionURL = urljoin(country, a['href']) #Joins the current url and the href to make an absolute URL
        region = httpx.get(regionURL, timeout=timeout) #navigate to the specific region

        while True:            
            try:
                citiesOuterContainer = SoupStrainer(class_='tab-pane active') #main container of the city links
                citiesContainerDoc = BeautifulSoup(region.text, 'html.parser', parse_only=citiesOuterContainer) #Retrieve container of the cities
                
                citiesInnerContainerDoc = citiesContainerDoc.find(class_='row') #Get the inner container of the links 

                cities = citiesInnerContainerDoc.find_all("a", href=True) #Retrieve each of the links of the cities
                
                visitCities(cities)

                nextButton = citiesContainerDoc.find(rel='next') #Find the next pagination button
                nextURL = urljoin(country, nextButton['href'])

                region = httpx.get(nextURL, timeout=timeout) #go to the next page (if there is any)
            except TypeError:
                break #Go to the next region when the next button does not exist anymore
            except AttributeError:
                #special case for berlin, because its a city already
                visitRegionCity(region)
                break
            except (ConnectionResetError, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError, httpx.RemoteProtocolError):
                print("Connection reset. Restarting the region...")
                continue #When the connection is reset, just restart the connection

def visitCities(cities):
    for city in cities:
        visitCity(city)

def visitCity(city):    
    path = 'savedlinks/[' + currentRegion + "] " + city.text + '.json'
    fromExcept = 0 #marker to show if we came from an except call
    currentPage = 0 #counter to count the page of the city; if cityCtr % 50 == 0, save it in the json file
    usingJSonPage = 0 #marker to show that we are using the json file currentPage

    #IF THE CITY IS SHOWN IN CACHE, SKIP THE CITY
    if(os.path.isfile(path)):
        f = open(path)
        data = json.load(f) #return json object as dictionary

        if(data['complete'] == 1):
            print("Found that " + city.text + " is already finished. Skipping...")
            return
        elif(data['currentPage'] != 0): #continue to the current page of the city
            #City URL Format: region_city_page#.php
            regionURLName = regionURL[:-4] #Separate the '.php' from the region name (last 4 chars)
            pageURL = regionURLName + '_' + city.text + '_' + str(data['currentPage']) + '.php'
            cityURL = urljoin(country, pageURL)
            print('URL is ' + cityURL)
            citySite = httpx.get(cityURL, timeout=timeout) #navigate to the specific city
            currentPage = data['currentPage']
            usingJSonPage = 1
    
    cityCachedData = {
        'currentPage': currentPage,
        'complete': 0
    }

    while True:
        try:
            print("Parsing city " + city.text) #For debugging purposes

            if(fromExcept == 0 and usingJSonPage == 0):
                cityURL = urljoin(country, city['href']) #Joins the current url and the href to make an absolute URL
                citySite = httpx.get(cityURL, timeout=timeout) #navigate to the specific city
            while True:
                try:
                    companiesContainer = SoupStrainer(class_='list-group') #list of the companies
                    companiesDoc = BeautifulSoup(citySite.text, 'html.parser', parse_only=companiesContainer) #Retrieve each of the links of the cities
                    
                    companies = companiesDoc.find_all("a", href=True) #Retrieve each of the links of the companies
                    
                    asyncio.run(getCompaniesData(companies)) #Get the data of each company; the information will be saved in companyData dictionary

                    appendData() #After getting all company info for that page, append it to the excel file

                    paginationContainer = SoupStrainer(class_='pagination') #get only the pagination div
                    paginationDoc = BeautifulSoup(citySite.text, 'html.parser', parse_only=paginationContainer) #get the html of the pagination

                    nextButton = paginationDoc.find(rel='next') #Find the next pagination button
                    nextURL = urljoin(country, nextButton['href'])
                    print(nextURL)
                    citySite = httpx.get(nextURL, timeout=timeout) #go to the next page (if there is any)
                    
                    currentPage += 1
                    cityCachedData['currentPage'] = currentPage #update the current page in the cached data
                    storeToCache(city.text, cityCachedData)
                except TypeError:
                    break #Go to the next region when the next button does not exist anymore

        except (ConnectionResetError, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError, httpx.RemoteProtocolError):
            print("Connection reset. Retrying...")
            fromExcept = 1 #set marker to continue where we came from
            continue #When the connection is reset, just restart the connection
        except Exception:
            traceback.print_exc() 
            print('An error occurred. Press enter to continue...')
            input()
            exit()
        else:
            break
    
    #store the cities in cache
    cityCachedData = {
        'currentPage': currentPage,
        'complete': 1 #set complete to 1 when we are done parsing all pages 
    }
    
    #store the cache in JSON file
    storeToCache(city.text, cityCachedData)

    cityCachedData.clear() #empty the dictionary
    print("Info of " + city.text + " stored in savedlinks folder")

def visitRegionCity(city):    
    path = 'savedlinks/[' + currentRegion + "] " + currentRegion + '.json'
    fromExcept = 0 #marker to show if we came from an except call
    currentPage = 0 #counter to count the page of the city; if cityCtr % 50 == 0, save it in the json file
    usingJSonPage = 0 #marker to show that we are using the json file currentPage

    #IF THE CITY IS SHOWN IN CACHE, SKIP THE CITY
    if(os.path.isfile(path)):
        f = open(path)
        data = json.load(f) #return json object as dictionary

        if(data['complete'] == 1):
            print("Found that " + currentRegion + " is already finished. Skipping...")
            return
        elif(data['currentPage'] != 0): #continue to the current page of the city
            #City URL Format: region_city_page#.php
            pageURL = currentRegion + '_' + currentRegion + '_' + str(data['currentPage'] + 1) + '.php'
            cityURL = urljoin(country, pageURL)
            city = httpx.get(cityURL, timeout=timeout) #navigate to the specific city
            currentPage = data['currentPage'] + 1

    cityCachedData = {
        'currentPage': currentPage,
        'complete': 0
    }

    while True:
        try:
            companiesContainer = SoupStrainer(class_='list-group') #list of the companies
            companiesDoc = BeautifulSoup(city.text, 'html.parser', parse_only=companiesContainer) #Retrieve each of the links of the cities
            
            companies = companiesDoc.find_all("a", href=True) #Retrieve each of the links of the cities
            
            asyncio.run(getCompaniesData(companies)) #Get the data of each company; the information will be saved in companyData dictionary
            appendData() #After getting all company info for that page, append it to the excel file
            
            paginationContainer = SoupStrainer(class_='pagination') #get only the pagination div
            paginationDoc = BeautifulSoup(city.text, 'html.parser', parse_only=paginationContainer) #get the html of the pagination

            nextButton = paginationDoc.find(rel='next') #Find the next pagination button
            nextURL = urljoin(country, nextButton['href'])
            print(nextURL)
            city = httpx.get(nextURL, timeout=timeout) #go to the next page (if there is any)
            
            currentPage += 1
            cityCachedData['currentPage'] = currentPage #update the current page in the cached data
            storeToCache(currentRegion, cityCachedData)

        except TypeError:
            break #Go to the next region when the next button does not exist anymore
        except (ConnectionResetError, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError, httpx.RemoteProtocolError):
                print("Connection reset. Retrying...")
                continue #When the connection is reset, just restart the connection
        except:
            traceback.print_exc() 
            print('An error occurred. Press enter to continue...')
            input()
            exit()
    
    #store the cities in cache
    cityCachedData = {
        'currentPage': currentPage,
        'complete': 1 #set complete to 1 when we are done parsing all pages 
    }

    #store the cache in JSON file
    storeToCache(currentRegion, cityCachedData)

    cityCachedData.clear() #empty the dictionary
    print("Info of " + currentRegion + " stored in savedlinks folder")

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
        for company in companyURLs:
            companyURL = urljoin(country, company['href'])
            tasks.append(getCompanyData(client, companyURL, rateLimit)) #add "visitCity" to the list of tasks needed to be done
        await asyncio.gather(*tasks)

async def getCompanyData(client, companyURL, limiter):
    async with limiter:
        while True:
            try:
                companyPage = await client.get(companyURL) #Parse the html of the url
                
                detailsContainer = SoupStrainer(class_="adressbox") #div element of that contains the info of company
                countryDoc = BeautifulSoup(companyPage.text, 'html.parser', parse_only=detailsContainer) #Gets the regions container (div) of the info

                #Retrieving the information
                companyName = countryDoc.find(itemprop='name').text
                try:
                    streetAddress = countryDoc.find(itemprop='streetAddress').text
                except:
                    streetAddress = ""

                try:
                    postalCode = countryDoc.find(itemprop='postalCode').text
                except:
                    postalCode = ""

                try:
                    addressLocality = countryDoc.find(itemprop='addressLocality').text
                except:
                    addressLocality = ""
                
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
            
            except(ConnectionResetError, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError, httpx.RemoteProtocolError):
                print("Connection reset. Retrying...")
                continue #When the connection is reset, just restart the connection
            except Exception: #for debugging purposes
                print('Error on URL: ' + str(companyURL))
                traceback.print_exc() 
                print('An error occurred. Press enter to continue...')
                input()
                exit()
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

def appendData():
    #append the items to the excel file
    companyDF = pd.DataFrame(companyData) #create df based on the dict

    tempDF = pd.read_excel('CompanyInfo.xlsx', index_col=0)
    tempDF = pd.concat([tempDF, companyDF], ignore_index=True)

    with pd.ExcelWriter('CompanyInfo.xlsx', engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        tempDF.to_excel(writer, sheet_name='Sheet1', engine='openpyxl')

    companyData.clear() #clear the dictionary
    constructCompanyData()

def constructCompanyData():
    global companyData
    companyData = {
        'Company Name': [],
        'Address': [],
        'Telephone': [],
        'Fax': [],
        'Email': [],
        'Website': []
    }

try:
    start_time = time.perf_counter()

    timeout = httpx.Timeout(None) #fine-tuning timeouts

    countries = ['http://www.firmendb.de/deutschland/index.php', 'http://www.firmendb.de/oesterreich/index.php', 'http://www.firmendb.de/schweiz/index.php']
    companyURLs = []
    companyURLCache = dict()

    constructCompanyData()

    for country in countries:
        visitCountry(country)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time

    print('Done after ' + str(elapsed_time) + 's!')
except Exception as e:
    logging.basicConfig(filename='crash-log.txt', encoding='utf-8', level=logging.DEBUG)
    logging.exception("main crashed. Error: %s", e)