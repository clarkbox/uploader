import os
import json
import logging
import shutil
import cgi

import splunk.admin as admin
from splunk import rest
from rest_error import RestError


APP_NAME = 'uploader'
CONF_FILE = 'uploader'
STANZA_NAME = 'paths'


logger = logging.getLogger('splunk')

import sys, os
sys.path.append(os.path.join('/opt/splunk','etc','apps','SA-VSCode','bin'))
import splunk_debug as dbg
dbg.enable_debugging(port=5686, timeout=120)


class UploaderException(Exception):
    pass


class ServiceRestcall(admin.MConfigHandler):
    '''
    Set up supported arguments
    '''

    savepath = '/my/upload/path'
    pendingPath = '/tmp/uploader_pending'

    # Static variables
    def setup(self):
        """
        Sets the input arguments
        :return:
        """

        # Set up the valid parameters
        for arg in ['resumableIdentifier', 'resumableFilename', 'resumableChunkNumber', 'resumableTotalSize', 'resumableChunkSize', 'resumableCurrentChunkSize', 'resumableRelativePath', 'resumableType', 'file']:
            self.supportedArgs.addOptArg(arg)

        self.get_paths()

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

        files.sort(self.sortFiles)

        for file in files:
            totalFiles = totalFiles+1
            chunks.append(os.path.join(tempDir, file))

        if (totalFiles * int(resumableChunkSize) > (int(resumableTotalSize) - int(resumableChunkSize))):
            if not os.path.exists(self.savepath):
                os.makedirs(self.savepath)
            logger.warning('assembling ' + resumableFilename +
                           ' from chunks in ' + tempDir)
            destination = open(os.path.join(
                self.savepath, resumableFilename), 'wb')
            for chunk in chunks:
                shutil.copyfileobj(open(chunk, 'rb'), destination)
            destination.close()
            shutil.rmtree(tempDir)

    def get_paths(self):
        # Get file paths from conf file
        try:
            _, serverContent = rest.simpleRequest(
                "/servicesNS/nobody/{}/configs/conf-{}?output_mode=json".format(APP_NAME, CONF_FILE), sessionKey=self.getSessionKey())
            data = json.loads(serverContent)['entry']
            for i in data:
                if i['name'] == STANZA_NAME:
                    self.savepath = i['content']['savepath']
                    self.pendingPath = i['content']['temppath']
                    break
        except Exception as e:
            logger.error(
                "Unable to fetch file paths from uploader.conf file." + str(e))
            raise

    def handleRequest(self, request_method, conf_info):

        logger.info("Just for testing, Vatsalllll.")
        # TODO - Need to remove above line.

        resumableChunkNumber = ''
        if resumableChunkNumber in self.callerArgs.data:
            resumableChunkNumber = self.callerArgs.data['resumableChunkNumber'][0]

        resumableChunkSize = ''
        if resumableChunkSize in self.callerArgs.data:
            resumableChunkSize = self.callerArgs.data['resumableChunkSize'][0]

        resumableCurrentChunkSize = ''
        if resumableCurrentChunkSize in self.callerArgs.data:
            resumableCurrentChunkSize = self.callerArgs.data['resumableCurrentChunkSize'][0]

        resumableFilename = ''
        if resumableFilename in self.callerArgs.data:
            resumableFilename = self.callerArgs.data['resumableFilename'][0]

        resumableIdentifier = ''
        if resumableIdentifier in self.callerArgs.data:
            resumableIdentifier = self.callerArgs.data['resumableIdentifier'][0]

        resumableRelativePath = ''
        if resumableRelativePath in self.callerArgs.data:
            resumableRelativePath = self.callerArgs.data['resumableRelativePath'][0]

        resumableTotalSize = ''
        if resumableTotalSize in self.callerArgs.data:
            resumableTotalSize = self.callerArgs.data['resumableTotalSize'][0]

        resumableType = ''
        if resumableType in self.callerArgs.data:
            resumableType = self.callerArgs.data['resumableType'][0]

        with open('/opt/splunk/etc/apps/uploader/local/logs.txt', 'a+') as f:
            # TODO - Need to remove this
            f.write("\n")
            f.write("callerArgs data: " + str(self.callerArgs.data))

        fs = None   # file field from request parameter
        # TODO - get above fields from self.callerArgs
        # TODO - Need to update kwargs with self.callerArgs

        if resumableIdentifier:
            logger.error('resumableIdentifier expected in args')
            with open('/opt/splunk/etc/apps/uploader/local/logs.txt', 'a+') as f:
                # TODO - Need to remove this
                f.write("\n")
                f.write("resumableIdentifier expected in args")
            raise RestError(500, "resumableIdentifier expected in args")
            # OLD - raise cherrypy.HTTPError(500)

        chunkFileName = resumableFilename + '.' + resumableChunkNumber
        chunkDir = os.path.join(self.pendingPath, resumableIdentifier)
        chunkFilePath = os.path.join(chunkDir, chunkFileName)
        tempChunkDir = os.path.join(chunkDir, 'temp')
        tempChunkFilePath = os.path.join(tempChunkDir, chunkFileName)

        if request_method == 'GET':
            if os.path.exists(chunkFilePath):
                with open('/opt/splunk/etc/apps/uploader/local/logs.txt', 'a+') as f:
                    # TODO - Need to remove this
                    f.write("\n")
                    f.write("File exist")
                return
                # OLD - return self.render_json([0])
            else:
                with open('/opt/splunk/etc/apps/uploader/local/logs.txt', 'a+') as f:
                    # TODO - Need to remove this
                    f.write("\n")
                    f.write("File not found")
                raise RestError(404, "Uploader: File not found.")
                # OLD - raise cherrypy.HTTPError(404)
                
        elif request_method == 'POST':
            with open('/opt/splunk/etc/apps/uploader/local/logs.txt', 'a+') as f:
                # TODO - Need to remove this
                f.write("\n")
                f.write("POST request")

            if(os.path.exists(os.path.join(self.savepath, resumableFilename))):
                with open('/opt/splunk/etc/apps/uploader/local/logs.txt', 'a+') as f:
                    # TODO - Need to remove this
                    f.write("\n")
                    f.write("File already exist.")
                conf_info['response']['errorcode'] = 1
                raise RestError(500, 'File named ' + resumableFilename + ' exists.')
                # OLD - cherrypy.response.status = 500
                # return self.render_json({'errorcode': 1,'message':'File named '+ resumableFilename +' exists.' })

            # TODO - I need to understand this below lines, where file is coming from and how that is FieldStorage's object?
            # fs = kwargs.get('file')
            if isinstance(fs, cgi.FieldStorage):
                if not os.path.exists(chunkDir):
                    try:
                        os.makedirs(chunkDir)
                    except:
                        logger.warning('failed creating directory '+chunkDir)
                        pass

                if not os.path.exists(tempChunkDir):
                    try:
                        os.makedirs(tempChunkDir)
                    except:
                        logger.warning(
                            'failed creating directory '+tempChunkDir)
                        pass

                newFile = open(tempChunkFilePath, 'wb')
                while 1:
                    buf = fs.file.read(1024)
                    if buf:
                        newFile.write(buf)
                    else:
                        break
                newFile.close()
                shutil.move(tempChunkFilePath, chunkFilePath)

                self.createFileFromChunks(
                    chunkDir, resumableFilename, resumableChunkSize, resumableTotalSize)
        else:
            with open('/opt/splunk/etc/apps/uploader/local/logs.txt', 'a+') as f:
                # TODO - Need to remove this
                f.write("\n")
                f.write("method not implemented.")
            raise RestError(404, "Uploader: This method is not implemented.")
            # OLD - raise cherrypy.HTTPError(404)
            # TODO - Check OLD to before final review

    def handleList(self, conf_info):
        self.handleRequest('GET', conf_info)

    def handleEdit(self, conf_info):
        self.handleRequest('POST', conf_info)


if __name__ == "__main__":
    admin.init(ServiceRestcall, admin.CONTEXT_APP_AND_USER)
