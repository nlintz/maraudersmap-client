import urllib

import webbrowser
from configuration import Settings
import signalStrength
from getpass import getuser

class Location(object):
    def __init__(self, encodedName, coordinate):
        self.coordinate = coordinate
        self.encodedName = encodedName

    def getReadableName(self):
        #XXX: This Doesn't work properly; from original code
        #TODO: Rewrite!

        # location strings look like WH,in,rm309
        location = self.encodedName.replace("OC", "MH") # Once upon a time, Milas hall was called Olin Center
        # XXX: Should be changed on server, probably
 
        try:
            building, inside, description = location.split(",")
        except:
            return None

        floor = building[2]
        building = building[0:2]

        if (inside == "in"):
            inside = "inside"
        elif (inside == "out"):
            inside = "outside"
        if (floor == "1"):
            floor = "1st"
        elif (floor == "2"):
            floor = "2nd"
        elif (floor == "3"):
            floor = "3rd"
        elif (floor == "4"):
            floor = "4th"
        elif (floor == "0"):
            floor = "LL"


        if (description.find("rm") != -1 or
            description.find("room") != -1 or
            description.find("Room") != -1 or
            description.find("ROOM") != -1):
            
            # this has a room
            description = description.replace("rm", "")
            description = description.replace("room", "")
            description = description.replace("Room", "")
            description = description.replace("ROOM", "")

            location = '%s %s%s' % (inside,building,description)
        else:
            if (floor != "LL"):
                location = '%s %s %s floor%s' % (inside,building,floor,description)
            else:
                location = '%s %s (%s) %s' % (inside,building,floor,description)
        
        return location

class Coordinate(object):
    __slots__ = ('x','y','w','distance')
    def __init__(self, x, y, w, distance=0):
        self.x = x
        self.y = y
        self.w = w # Which map the coord refers to (1 or 2)
        self.distance = distance

# XXX: Sketchy global variable to get around server api requirement of getting location without posting it
# XXX: Using this method until the server api gets fixed. I know it is REALLY BAD - Julian
global lastSignalStrengthString
lastSignalStrengthString = None 

def openMap():
    """
    Brings up the marauder's map in a web browser
    """
    webbrowser.open(Settings.WEB_ADDRESS)

def sendToServer(strPHPScript, dictParams):
    '''
    Uses urllib to send a dictionary to a PHP script on the server specified in configuration.py 

    Returns a tuple (successBOOL, responseSTR/explanation_of_failureSTR)
    '''

    # Construct url with the parameters specified in the dictionary
    strUrl = "%s/%s?%s" % (Settings.SERVER_ADDRESS, strPHPScript, urllib.urlencode(dictParams))
    print strUrl 
    
    try:
        u = urllib.urlopen(strUrl)
        ret = u.read().strip()
        u.close()
    except:
        return False, 'Could not connect to server!'
    
    #See if successful
    if not ret.startswith('success:'):
        return False, ret
    else:
        return True, ret[len('success:'):]

def __update(username, currPlaceName = None, status=None, refresh=True):
    """
    Update can tell you where you are or tell the server where you are, without affecting
    the database.
    """

    #XXX: Using this method until the server api gets fixed. I know it is REALLY BAD - Julian
    global lastSignalStrengthString
    if refresh or lastSignalStrengthString == None:
        signalStrengthNodes = signalStrength.getAvgSignalNodes(samples=3, tsleep=0.15)
        signalStrengthStr = ";".join([str(node) for node in signalStrengthNodes])
        lastSignalStrengthString = signalStrengthStr
    else:
        signalStrengthStr = lastSignalStrengthString

    dictSend = dict()
    dictSend['username'] = username
    dictSend['data'] = signalStrengthStr
    dictSend['platform'] = __getPlatform()
    
    if currPlaceName:
        dictSend['placename'] = currPlaceName  
        
    if status:
        dictSend['status'] = status

    flag, result = sendToServer('update.php', dictSend)
    if not flag:
        print 'Error:', result
        return flag, result    
    potentialLocations = list()
    for point in result.split(';'):
        if len(point) == 0: continue
        # placename , distance , mapx, mapy, mapw            
        point = point.split('|')
        distanceFromPlace = float(point[1])        
        x,y,w = int(point[2]), int(point[3]), int(point[4])
        coord = Coordinate(x, y, w, distance=distanceFromPlace)
        placeName = point[0]
        potentialLocations.append(Location(placeName, coord))

    return True, potentialLocations


def getLocation():
    '''
    Get location from server.
    
    Returns a list of potential locations, 
    sorted from most to least likely.
    '''
    
    return __update(getuser())

def postLocation(placeName):
    '''
    Post encoded location to server, without changing the database.
    
    Returns a list of potential locations, 
    sorted from most to least likely.
    '''

    print "Name to post:", placeName
    
    return __update(getuser(), currPlaceName=placeName)
    
def weakPostLocation(placeName):
    '''
    Post encoded location to server, without changing the database and without refreshing signal strength.
    
    Returns a list of potential locations, 
    sorted from most to least likely.
    '''

    print "Name to post:", placeName
    
    return __update(getuser(), currPlaceName=placeName, refresh=False)

def __getPlatform():
    '''
    Return a standard readable string based on the operating system.
    '''
    import sys
    if sys.platform.startswith('darwin'):
        return 'mac'
    elif sys.platform.startswith('win'):
        return 'win'
    elif sys.platform.startswith('linux'):
        return 'linux'
    return sys.platform # non-standard platform

def do_train(placename, coord):
    #XXX: UNTESTED
    '''
    Tell server that a location in x,y,w space maps to a certain signal strength dictionary (data) and
    encoded placename string.
    This actually changes the database and can be used to create novel locations or improve the
    database entry for existing locations.
    '''

    mapx, mapy, mapw = coord.x, coord.y, coord.w

    signalStrengthNodes = signalStrength.getAvgSignalNodes(samples=3, tsleep=0.15)
    signalStrengthStr = ";".join([str(node) for node in signalStrengthNodes])
    
    #XXX: Using this method until the server api gets fixed. I know it is REALLY BAD - Julian    
    global lastSignalStrengthString
    lastSignalStrengthString = signalStrengthStr

    dictSend = {'username':getuser(), 'placename':placename,'mapx':mapx,'mapy':mapy, 'mapw':mapw, 'data':signalStrengthStr}
    dictSend['platform'] = __getPlatform()
        
    retStatus, result = sendToServer('train.php', dictSend)
    print dictSend
    if not retStatus:
        print 'Error:', result
        return retStatus, result
        
    return True, result

def unserializePersonData(serverResponseString):
    '''
    Takes in a pipe-separated string and 
    outputs a dictionary with the keys
    'username', 'placename', 'status', and 'lastupdate'
    '''
    personData = dict()
    if serverResponseString == 'nobody': 
        return 'nobody'
    serverResponseArray = serverResponseString.split('|')
    personData['username'] = serverResponseArray[0]
    personData['placename'] = serverResponseArray[1]
    personData['status'] = serverResponseArray[2]
    personData['lastupdate'] = serverResponseArray[3]
    return personData

def do_query(username):
    #XXX: UNTESTED
    '''
    Get a dictionary containing
    username, placename, status, and lastupdate
    of person with username
    '''
    flag, result = sendToServer('query.php', {'username':username})
    if not flag:
        print 'Error:', result
        return flag, result
    
    result = unserializePersonData(result)
    return True, result

def do_datapointexistence(placename):
    #XXX: UNTESTED
    '''
    Check if a point with a specific encoded placename exists
    '''
    flag, result = data_connections.sendToServer('pointexistence.php', {'placename':placename})
    if not flag:
        print 'Error:', result
        return flag, result
        
    if result=='true': return True, True
    else: return True, False

def do_cloak(username):
    #XXX: UNTESTED
    '''
    Tell the server to stop displaying a user with username on the map.

    This is kind of sketchy and probably shoudn't be possible?
    '''
    flag, result = sendToServer('cloak.php', {'username':username})
    if not flag:
        print 'Error:', result
        return flag, result
    
    return flag, result

if __name__=='__main__':
    #~ do_update('bfisher','righthere')
    print do_datapointexistence('AC30,out,rm308')
    print do_datapointexistence('AC30,,out,rm308')
