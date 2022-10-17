import re, os, sys, getopt, time, csv, pprint
from netmiko import ( ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException,)
import concurrent.futures

startTime = time.time()

# LOGIN CREDENTIALS 
# Set via ENV variables or you can set them manually below. 
# Note: ENV variables, if set, will override manually set credentials below.
#------------------------------------------
sshUser = "JohnDoe"
sshPass = "JohnDoePassword"
sshSecret = "JohnDoeEnablePassword"

env1 = "TACACS_USER"
env2 = "TACACS_PASS"
env3 = "TACACS_SECRET"
if env1 in os.environ:
    sshUser = os.environ.get(env1)
if env2 in os.environ:
    sshPass = os.environ.get(env2)
if env3 in os.environ:
    sshSecret = os.environ.get(env3)

#---------parse-args--------------------------------

argList = sys.argv[1:]
if len(argList) < 1:
    print(f'\n Error: must supply at least one argument \n')
    sys.exit()
options = "hv:i:"
try:
    args, value = getopt.getopt(argList, options)
    for arg, val in args:
        if arg in ("-h"):
            printhelp()
            sys.exit()
        elif arg in ("-i"):
            inFile = val
except getopt.error as err:
    print("\nError: " , str(err) , "\n")
    sys.exit()

#-------------defs----------------------------
def printhelp():
    print(f'\nDESCRIPTION:\n This script collects lldp neighbor information from physical interfaces. ')
    print(f'\nUSAGE:\n python3 <scriptname> -i <hostsFile>')
    print(f'  <scriptname>   : name of python script')
    print(f'  <hostsFile>    : text file list of ip addresses, one per line')
    print(f'\nLOGIN CREDENTIALS:\n Set as env variables or can be set manually at top of script.\n')

def fetchIPs(inputFile):
    ipFile = inputFile
    with open(ipFile) as devices:
        addresses = devices.read().splitlines()
    return addresses

def removeSubintNeighs(nlist):
    ''' Remove neighbors connected via subinterfaces from neigh list '''
    newList = []
    for line in nlist:
        item = line.split(':')
        subInterface = re.search(r'\.([0-9]*)$', str(item[2]))
        if not subInterface:
            newList.append(line)
            # UNCOMMENT below line to print lldp neigh info as it is found
            #print("{0:<22} {1:<8}     {2:<8} {3}".format(item[0],item[1],item[2],item[3]))
    return newList

def cleanupHostname(hostname="hostX"):
    ''' Function to cleanup hostname captured via lldp '''
    dotChar = hostname.find(".")
    hostname = hostname[0:dotChar]
    return hostname


def getNeighInfo(ip):
    try:
        device = {
            "device_type": "cisco_ios",
            "host": ip,
            "username": sshUser,
            "password": sshPass,
            "secret": sshSecret,
        }
        ssh = ConnectHandler(**device)
        ssh.enable()
    except NetmikoTimeoutException as error:
        print(f'Error: {error}')
    except NetmikoAuthenticationException as error:
        print(f'AuthenticationError: {error}')

    cmd1 = "show run | include hostname"
    cmd2 = "show lldp neighbors detail | include Local Intf|Port id|System Name"
    neighCount = 0

    with ConnectHandler(**device) as ssh:
        ssh.enable()

        # Send cmds 
        output1 = ssh.send_command(cmd1)
        output2 = ssh.send_command(cmd2)
        ssh.disconnect()
        
        # Parse cmd1 output for hostname
        result1 = output1.splitlines()
        fline = result1[0].split()
        localName = fline[1]
        
        #Parse cmd2 output for lldp neigh info
        result2 = output2.splitlines()
        x = 1
        device = {}
        neighList = []
        neighStr = ""
        for line in result2:
            items = line.split(': ',1)
            if "local intf" in items[0].lower():
                neighStr = str(items[1])
            elif "port id" in items[0].lower():
                neighStr = neighStr + ":" + str(items[1]) 
            elif "system name" in items[0].lower():
                neighName = cleanupHostname(str(items[1]))
                neighStr = localName + ":" + neighStr + ":" + neighName
                neighList.append(neighStr)
                neighStr = ""
        
        # Total lldp neighbor count
        neighCountTotal = len(neighList)
        # Remove subinterface neighbors from lldp neigh list 
        neighList = removeSubintNeighs(neighList)
        # New lldp neighbor count
        neighCount = len(neighList)

        # UNCOMMENT below line to print count of lldp neighbors found 
        #print(f'{localName:<22} {ip:<12} {neighCount:>10} lldp phy interface neighbors found out of {neighCountTotal}.')

    return neighList
#-----------------------------------------
try:

    ip_addresses = fetchIPs(inFile)
    ipNum = 1
    ipNumTotal = len(ip_addresses)
    lldpNeigh = []
    with concurrent.futures.ThreadPoolExecutor() as exe:
        futures = []
        for ip in ip_addresses:
            futures.append(exe.submit(getNeighInfo, ip))
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            lldpNeigh.extend(res)
            print(f' {ipNum:>3} of {ipNumTotal:<4} completed')
            ipNum += 1

    with open('output-lldpneigh.csv', 'w') as out:
        colHeaders = "LocalName,LocalIntfc,NeighIntfc,NeighName\n"
        out.write(colHeaders)
        for line in lldpNeigh:
            rowText = line.replace(':',',') + '\n'
            out.write(rowText)

except (concurrent.futures.TimeoutError, concurrent.futures.CancelledError) as error:
    print(f'{error}')
except KeyboardInterrupt as error:
    print(f'\n ERROR: interrupted by user - KeyboardInterrupt\n')
    sys.exit()

#-----------------------------------------
endTime = time.time()
runTime = round((endTime - startTime),2)
print(f'-----------------------')
print(f'RunTime: {runTime:<3} sec\n')



