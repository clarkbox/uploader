import os
import json
import logging
import shutil

import splunk.admin as admin
from splunk import rest


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
                    logger.info("Got savepath and pending path from uploader.conf. savepath={} pendingpath={}".format(self.savepath, self.pendingPath))
                    break
        except Exception as e:
            logger.error("Unable to fetch file paths from uploader.conf file." + str(e))
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
            files.append({'name': fname, 'size': size, 'isFile': isFile, 'finished': True})

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
                    files.append({'name': fname, 'size': size, 'isFile': isFile, 'finished': False, 'parts': parts})

        conf_info['response']['files'] = json.dumps(files)

    
    def action_remove(self, conf_info, fname):
        os.remove(os.path.join(self.savepath, fname))
        conf_info['response']['file_name'] = fname
    

    def action_removeall(self, conf_info):
        if os.path.exists(self.savepath):
            logger.warning('purge uploaded files '+ self.savepath)
            shutil.rmtree(self.savepath)
        conf_info['response']['success'] = [0]


    def action_removepending(self, conf_info):
        if os.path.exists(self.pendingPath):
            logger.warning('purge pending files '+ self.pendingPath)
            shutil.rmtree(self.pendingPath)
        conf_info['response']['success'] = [0]


    def handleList(self, conf_info):
        self.get_paths()

        data = json.loads(self.callerArgs['data'][0])
        action = data['action']
        filename = None
        if 'filename' in data:
            filename = data['filename']
        
        if action == 'list':
            self.action_list(conf_info)
        elif action == 'remove':
            self.action_remove(conf_info, filename)
        elif action == 'removeall':
            self.action_removeall(conf_info)
        elif action == 'removepending':
            self.action_removepending(conf_info)


    def handleEdit(self, conf_info):
        logger.warning("Post method is not implemented.")        


if __name__ == "__main__":
    admin.init(ServiceRestcall, admin.CONTEXT_APP_AND_USER)
