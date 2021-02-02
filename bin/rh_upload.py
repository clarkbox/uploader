import sys
import os
import json
import logging
import shutil
import re
if (sys.version_info > (3, 0)):
     import functools   # only for python3

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


import splunk
from splunk import rest


APP_NAME = 'uploader'
CONF_FILE = 'uploader'
STANZA_NAME = 'paths'


logger = logging.getLogger('splunk')


class Upload(splunk.rest.BaseRestHandler):
    """Class for getting UI validation message through custom endpoint."""

    def sortFiles(self, a, b):
        a = a[a.rfind('.')+1:]
        b = b[b.rfind('.')+1:]
        return int(a)-int(b)

    def createFileFromChunks(self, tempDir, resumableFilename, resumableChunkSize, resumableTotalSize):
        totalFiles = 0
        chunks = []
        possibleFiles = os.listdir(tempDir)
        files = []
        for f in possibleFiles:
            if os.path.isfile(os.path.join(tempDir, f)) and resumableFilename in f:
                try:
                    int(f[f.rfind('.')+1:])
                    files.append(f)
                except:
                    pass

        if (sys.version_info > (3, 0)):
            files.sort(key = functools.cmp_to_key(self.sortFiles))
        else:
            files.sort(self.sortFiles)

        for file in files:
            totalFiles = totalFiles+1
            chunks.append(os.path.join(tempDir, file))

        if (totalFiles * int(resumableChunkSize) > (int(resumableTotalSize) - int(resumableChunkSize))):
            if not os.path.exists(self.savepath):
                os.makedirs(self.savepath)
            logger.warning('assembling ' + resumableFilename + ' from chunks in ' + tempDir)
            destination = open(os.path.join(self.savepath, resumableFilename), 'wb')
            for chunk in chunks:
                shutil.copyfileobj(open(chunk, 'rb'), destination)
            destination.close()
            shutil.rmtree(tempDir)


    def get_paths(self):
        # Get file paths from conf file
        try:
            _, serverContent = rest.simpleRequest(
                "/servicesNS/nobody/{}/configs/conf-{}?output_mode=json".format(APP_NAME, CONF_FILE), sessionKey=self.sessionKey)
            data = json.loads(serverContent)['entry']
            for i in data:
                if i['name'] == STANZA_NAME:
                    self.savepath = i['content']['savepath']
                    self.pendingPath = i['content']['temppath']
                    logger.info("Got savepath and pending path from uploader.conf. savepath={} pendingpath={}".format(self.savepath, self.pendingPath))
                    break
        except Exception as e:
            logger.error("Unable to fetch file paths from uploader.conf file." + str(e))
            raise
    

    def raise_error(self, error_code=500, message=None):
        """
        Use this function to raise HTTP error
        """
        self.response.setHeader('content-type', 'application/json')
        self.response.setStatus(error_code)
        if message:
            response = json.dumps('{"message": "' + message + '"}')
            self.response.write(response)
    

    def parse_payload(self, content_type, payload):
        """
        This function parses the payload from normal format to key-value pair dictionary.
        Call this function like:
            content_type = self.request['headers']['content-type']
            payload_in_parts = self.parsePayload(content_type, self.request['payload'])
        """
        posted_parts = {}
        if re.match('application/x-www-form-urlencoded', content_type):
            posted_parts = urlparse.parse_qs(payload)
        elif re.search('form-data', content_type):
            # First, determine the separator (boundary)
            parsedBoundary = re.search(r'boundary\s*=\s*(?P<boundary>\S+)', content_type)
            boundary = parsedBoundary.group('boundary')
            # Now, split the payload
            parts = payload.split('--' + boundary)
            for part in parts:
                try:
                    parsedPart = re.search('Content-Disposition: form-data; name=\"(?P<name>[^\"]+)\"(; filename=\"(?P<filename>[^\"]+)\")?(\r?\nContent-Type:[^\r\n]*)?(\r?\nContent-Length:[^\r\n]*)?\r?\n\r?\n(?P<content>[^$]*)', part)
                    content = parsedPart.group('content')[:-2] if parsedPart.group('content')[-2] == '\r' else parsedPart.group('content')[:-1]
                    posted_parts[parsedPart.group('name')] = content    # .strip()
                except:
                    pass
        return posted_parts


    def handle_request(self, request_method):

        payload_in_parts = None
        if request_method == 'GET':
            payload_in_parts = self.request['query']
        elif request_method == 'POST':
            content_type = self.request['headers']['content-type']
            payload_in_parts = self.parse_payload(content_type, self.request['payload'])

        # Get save path and pending path        
        self.get_paths()

        resumableChunkNumber = ''
        if 'resumableChunkNumber' in payload_in_parts:
            resumableChunkNumber = payload_in_parts['resumableChunkNumber']

        resumableChunkSize = ''
        if 'resumableChunkSize' in payload_in_parts:
            resumableChunkSize = payload_in_parts['resumableChunkSize']

        """
        # Unused variable
        resumableCurrentChunkSize = ''
        if 'resumableCurrentChunkSize' in payload_in_parts:
            resumableCurrentChunkSize = payload_in_parts['resumableCurrentChunkSize']
        """

        resumableFilename = ''
        if 'resumableFilename' in payload_in_parts:
            resumableFilename = payload_in_parts['resumableFilename']

        resumableIdentifier = ''
        if 'resumableIdentifier' in payload_in_parts:
            resumableIdentifier = payload_in_parts['resumableIdentifier']

        """
        # Unused variable
        resumableRelativePath = ''
        if 'resumableRelativePath' in payload_in_parts:
            resumableRelativePath = payload_in_parts['resumableRelativePath']
        """

        resumableTotalSize = ''
        if 'resumableTotalSize' in payload_in_parts:
            resumableTotalSize = payload_in_parts['resumableTotalSize']

        """
        # Unused variable
        resumableType = ''
        if 'resumableType' in payload_in_parts:
            resumableType = payload_in_parts['resumableType']
        """
        
        file = ''
        if 'file' in payload_in_parts:
            file = payload_in_parts['file']


        if not resumableIdentifier:
            logger.error('resumableIdentifier expected in args')
            self.raise_error(500, "resumableIdentifier expected in args")
            # OLD - raise cherrypy.HTTPError(500)

        chunkFileName = resumableFilename + '.' + resumableChunkNumber
        chunkDir = os.path.join(self.pendingPath, resumableIdentifier)
        chunkFilePath = os.path.join(chunkDir, chunkFileName)
        tempChunkDir = os.path.join(chunkDir, 'temp')
        tempChunkFilePath = os.path.join(tempChunkDir, chunkFileName)

        if request_method == 'GET':
            logger.debug("rh_upload: GET request.")
            if os.path.exists(chunkFilePath):
                logger.info("File exist.")
                return   # OLD - return self.render_json([0])
            else:
                logger.info("rh_upload: file not found.")
                self.raise_error(404, "Uploader: File not found.")
                # OLD - raise cherrypy.HTTPError(404)
                
        elif request_method == 'POST':
            logger.debug("rh_upload: POST request.")

            if(os.path.exists(os.path.join(self.savepath, resumableFilename))):
                logger.warning("File {} already exist.".format(resumableFilename))
                self.raise_error(500, 'File named ' + resumableFilename + ' exists.')
                # OLD - cherrypy.response.status = 500
                # OLD - return self.render_json({'errorcode': 1,'message':'File named '+ resumableFilename +' exists.' })

            if file:     # OLD - if isinstance(fs, cgi.FieldStorage):
                if not os.path.exists(chunkDir):
                    try:
                        os.makedirs(chunkDir)
                    except Exception as e:
                        logger.warning('failed creating directory '+chunkDir + ' Reason: ' + str(e))
                        pass

                if not os.path.exists(tempChunkDir):
                    try:
                        os.makedirs(tempChunkDir)
                    except Exception as e:
                        logger.warning('failed creating directory '+tempChunkDir + ' Reason: ' + str(e))
                        pass

                newFile = open(tempChunkFilePath, 'a+')
                
                '''
                # OLD
                while 1:
                    buf = fs.file.read(1024)
                    if buf:
                        newFile.write(buf)
                    else:
                        break
                '''
                newFile.write(file)

                newFile.close()
                shutil.move(tempChunkFilePath, chunkFilePath)

                self.createFileFromChunks(
                    chunkDir, resumableFilename, resumableChunkSize, resumableTotalSize)
            else:
                logger.error("File attribute not present in the POST request.")
        else:
            logger.error("HTTP Method not implemented.")
            self.raise_error(404, "Uploader: This method is not implemented.")
            # OLD - raise cherrypy.HTTPError(404)


    def handle_GET(self):
        self.handle_request("GET")

    def handle_POST(self):
        self.handle_request("POST")
