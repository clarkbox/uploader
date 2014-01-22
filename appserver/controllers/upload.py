import logging
import os
import sys
import json
import cgi
import cherrypy
import splunk
import splunk.appserver.mrsparkle.controllers as controllers
import splunk.appserver.mrsparkle.lib.util as util
import splunk.util
import splunk.clilib.cli_common
import shutil
from splunk.appserver.mrsparkle.lib.decorators import expose_page
from splunk.appserver.mrsparkle.lib.routes import route
from splunk.appserver.mrsparkle.lib import jsonresponse

logger = logging.getLogger('splunk')
settings = splunk.clilib.cli_common.getConfStanza('app', 'ui')
savepath = settings['savepath']
pendingPath = settings['temppath']

class upload(controllers.BaseController):

    def render_json(self, response_data, set_mime="text/json"):
        cherrypy.response.headers["Content-Type"] = set_mime
        if isinstance(response_data, jsonresponse.JsonResponse):
            response = response_data.toJson().replace("</", "<\\/")
        else:
            response = json.dumps(response_data).replace("</", "<\\/")
        return " " * 256  + "\n" + response
    
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
   
    @route('/')
    @expose_page(must_login=True, methods=['GET','POST'])
    def status(self, **kwargs):        
        if(not 'resumableIdentifier' in kwargs):
            logger.error('resumableIdentifier expected in args')
            raise cherrypy.HTTPError(500)
        
        chunkFileName = kwargs['resumableFilename'] + '.' + kwargs['resumableChunkNumber']
        chunkDir = os.path.join(pendingPath, kwargs['resumableIdentifier'])
        chunkFilePath = os.path.join(chunkDir, chunkFileName)
        tempChunkDir = os.path.join(chunkDir, 'temp')
        tempChunkFilePath = os.path.join(tempChunkDir, chunkFileName)
        
        if cherrypy.request.method == 'GET':
            if os.path.exists(chunkFilePath):
                return self.render_json([0])
            else:
                raise cherrypy.HTTPError(404)
            
        elif cherrypy.request.method == 'POST':
            
            if(os.path.exists(os.path.join(savepath, kwargs['resumableFilename']))):
                cherrypy.response.status = 500    
                return self.render_json({'errorcode': 1,'message':'File named '+ kwargs['resumableFilename'] +' exists.' })
        
            fs = kwargs.get('file')
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
                
                self.createFileFromChunks(chunkDir, kwargs['resumableFilename'], kwargs['resumableChunkSize'], kwargs['resumableTotalSize']);
        else:
            raise cherrypy.HTTPError(404)
   