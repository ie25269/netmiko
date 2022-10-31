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

# output csv file name or use the arg -o <name>
outFile = "output-show-cmd.csv"

argList = sys.argv[1:]
if len(argList) < 1:
    print(f'\n Error: must supply at least one argument \n')
    sys.exit()
options = "hvo:i:"
try:
    args, value = getopt.getopt(argList, options)
    for arg, val in args:
        if arg in ("-h"):
            printhelp()
            sys.exit()
        elif arg in ("-i"):
            inFile = val
        elif arg in ("-o"):
            outFile = val
except getopt.error as err:
    print("\nError: " , str(err) , "\n")
    sys.exit()

#-------------defs----------------------------
def printhelp():
    print(f'\nDESCRIPTION:\n This script collects output from a show command and saves it to csv file. ')
    print(f'\nUSAGE:\n python3 <scriptname> -i <hostsFile> -o <output-filename> [OPTIONAL]')
    print(f'  <scriptname>   : name of python script')
    print(f'  <hostsFile>    : text file list of ip addresses, one per line')
    print(f'\nLOGIN CREDENTIALS:\n Set as env variables or can be set manually at top of script.\n')

def fetchIPs(inputFile):
    ipFile = inputFile
    with open(ipFile) as devices:
        addresses = devices.read().splitlines()
    return addresses


def getShowOutput(ip):
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
    cmd2 = "show ip vrf interface"

    with ConnectHandler(**device) as ssh:
        ssh.enable()

        # Send cmds 
        output1 = ssh.send_command(cmd1)
        output2 = ssh.send_command(cmd2)
        ssh.disconnect()
        outDict = {}
        
        # Parse cmd1 output for hostname
        result1 = output1.splitlines()
        fline = result1[0].split()
        localName = fline[1]
        
        # Parse cmd2 output 
        intList = []
        result2 = output2.splitlines()
        text = ''
        for line in result2:
            items = line.split()
            itemString = ""
            for i in items :
                text = i.strip()
                itemString = itemString + text + ","
            intList.append(itemString)
        outDict[localName] = intList

    return outDict
#-----------------------------------------
try:

    ip_addresses = fetchIPs(inFile)
    ipNum = 1
    ipNumTotal = len(ip_addresses)
#   Create Result List
#   outputList = []
#   Create Result Dict
    outputDict = {}

    with concurrent.futures.ThreadPoolExecutor() as exe:
        futures = []
        for ip in ip_addresses:
            futures.append(exe.submit(getShowOutput, ip))
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            outputDict.update(res)
            print(f' {ipNum:>3} of {ipNumTotal:<4} completed')
            ipNum += 1

# Save output from Result Dictionary
    with open(outFile, 'w') as out:
        header = "COL1,COL2,COL3,COL4,COL5\n"
        out.write(header)
        for dev in outputDict:
            iList = outputDict[dev]
            for i in iList:
                rowText = dev + "," + i + '\n'
                out.write(rowText)

# Save output from Result List
#    with open('output-show-cmd.csv', 'w') as out:
#        for line in outputList:
#            rowText = line + '\n'
#            out.write(rowText)
    

except (concurrent.futures.TimeoutError, concurrent.futures.CancelledError) as error:
    print(f'{error}')
except KeyboardInterrupt as error:
    print(f'\n ERROR: interrupted by user - KeyboardInterrupt\n')
    sys.exit()

#-----------------------------------------
endTime = time.time()
runTime = round((endTime - startTime),2)
print(f'-----------------------')
print(f'RunTime:    {runTime} sec')
print(f'OutputFile: {outFile}\n')



