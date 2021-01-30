import os
import json
import logging
import shutil

import splunk.admin as admin
from splunk import rest
from splunk.appserver.mrsparkle.lib import jsonresponse


APP_NAME = 'uploader'
CONF_FILE = 'uploader'
STANZA_NAME = 'paths'


logger = logging.getLogger('splunk')


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
        for arg in ['data']:
            self.supportedArgs.addOptArg(arg)
        
        self.get_paths()


    def render_json(self, response_data, set_mime="text/json"):
        if isinstance(response_data, jsonresponse.JsonResponse):
            response = response_data.toJson().replace("</", "<\\/")
        else:
            response = json.dumps(response_data).replace("</", "<\\/")
        return " " * 256 + "\n" + response
    

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
            if os.path.isfile(os.path.join(tempDir,f)) and resumableFilename in f:
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
            if not os.path.exists(savepath):
                os.makedirs(savepath) 
            logger.warn('assembling '+ resumableFilename +' from chunks in '+ tempDir)
            destination = open(os.path.join(savepath, resumableFilename), 'wb')
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
    
    def action_list(self, conf_info):
                files = []
        savedFiles = []
        if os.path.exists(self.savepath):
            savedFiles = os.listdir(self.savepath)

        for fname in savedFiles:
            size = 0
            saveFile = os.path.join(self.savepath, fname)
            isFile = os.path.isfile(saveFile)
            if(isFile and fname[0] != '.'):
                size = os.path.getsize(saveFile)
            files.append({'name': fname, 'size': size,
                          'isFile': isFile, 'finished': True})

        pendingFiles = []
        if os.path.exists(self.pendingPath):
            pendingFiles = os.listdir(self.pendingPath)

        for fname in pendingFiles:
            size = 0
            isFile = os.path.isfile(os.path.join(self.pendingPath, fname))
            pendingFolder = os.path.join(self.pendingPath, fname)
            if(not isFile and fname[0] != '.'):
                chunks = os.listdir(pendingFolder)
                size = 0
                parts = 0
                for chunk in chunks:
                    try:
                        chunkNumber = int(chunk[chunk.rfind('.')+1:])
                    except:
                        chunkNumber = -1

                    if(chunkNumber > 0):
                        chunkPath = os.path.join(pendingFolder, chunk)
                        if(os.path.isfile(chunkPath) and chunk[0] != '.'):
                            parts = parts + 1
                            size = size + os.path.getsize(chunkPath)
                            fname = chunk[:chunk.rfind('.')]

                if(fname):
                    files.append(
                        {'name': fname, 'size': size, 'isFile': isFile, 'finished': False, 'parts': parts})

        return self.render_json(files)
        # TODO - Need to update this return statement with adding data to conf_info object.
        # something like this - conf_info['action']['api_id'] = api_id
        # We also need to update the JS file accordingly
        # index.js - $.ajax('/custom/uploader/service/list')
    
    
    def action_remove(conf_file, path):
        # TODO - Need to extract fname field
        fname = ''
        os.remove(os.path.join(self.savepath,fname))
        return self.render_json(fname)
        # TODO - $.ajax('/custom/uploader/service/remove/'
    

    def action_removeall(conf_file):
        if os.path.exists(self.savepath):
            logger.warn('purge uploaded files '+ self.savepath)
            shutil.rmtree(self.savepath)
        return self.render_json([0])
        # TODO - $.ajax('/custom/uploader/service/removeall'
    
    def action_removepending(self, conf_info):
        if os.path.exists(self.pendingPath):
            logger.warn('purge pending files '+ self.pendingPath)
            shutil.rmtree(self.pendingPath)
            
        return self.render_json([0])


    def handleRequest(self, request_method, conf_info):
        # TODO - Need to check self.callerArgs should have some value that determines the path
        # like $.ajax('/custom/uploader/service/removepending')
        action = ''
        path = ''
        
        resumableIdentifier = None
        resumableFilename = None
        resumableChunkNumber = None
        resumableTotalSize = None
        fs = None   # file field from request parameter
        # TODO - get above fields from self.callerArgs
        # TODO - Need to update kwargs with self.callerArgs

 
        if resumableIdentifier:
            logger.error('resumableIdentifier expected in args')
            # raise cherrypy.HTTPError(500)
            # TODO - Return the value with error message
            # conf_info['error']['error_message'] = 'resumableIdentifier expected in args'
            # return
        
        chunkFileName = resumableFilename + '.' + resumableChunkNumber
        chunkDir = os.path.join(pendingPath, resumableIdentifier)
        chunkFilePath = os.path.join(chunkDir, chunkFileName)
        tempChunkDir = os.path.join(chunkDir, 'temp')
        tempChunkFilePath = os.path.join(tempChunkDir, chunkFileName)
        
        if request_method == 'GET':
            if os.path.exists(chunkFilePath):
                return self.render_json([0])
            else:
                # raise cherrypy.HTTPError(404)
                # TODO - raise the new rest error instead
                return
            
        elif request_method == 'POST':
            
            if(os.path.exists(os.path.join(savepath, resumableFilename))):
                # cherrypy.response.status = 500    
                # TODO - raise the new rest error instead
                return self.render_json({'errorcode': 1,'message':'File named '+ resumableFilename +' exists.' })
        
            # fs = kwargs.get('file')
            if isinstance(fs, cgi.FieldStorage):
                if not os.path.exists(chunkDir):
                    try:
                        os.makedirs(chunkDir)
                    except:
                        logger.warn('failed creating directory '+chunkDir)
                        pass
                
                if not os.path.exists(tempChunkDir):
                    try:
                        os.makedirs(tempChunkDir)
                    except:
                        logger.warn('failed creating directory '+tempChunkDir)
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
                
                self.createFileFromChunks(chunkDir, resumableFilename, resumableChunkSize, resumableTotalSize)
        else:
            pass
            # raise cherrypy.HTTPError(404)
            # TODO - Return the value with error message
            # conf_info['error']['error_message'] = 'This method is not implemented'
            # return


    def handleList(self, conf_info):
        self.handleRequest('GET', conf_info)      

    def handleEdit(self, conf_info):
        self.handleRequest('POST', conf_info)    


if __name__ == "__main__":
    admin.init(ServiceRestcall, admin.CONTEXT_APP_AND_USER)
