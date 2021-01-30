require([
    'jquery',
    'underscore',
    'resumable',
    'splunkjs/mvc/utils',
    'splunkjs/mvc',
    'splunkjs/mvc/searchmanager',
    'splunkjs/mvc/simplexml/ready!'
], function ($, underscore, Resumable, utils, mvc, SearchManager) {
    // TODO - Check proper import of Resumable


    let formkey = `${utils.getFormKey()|h}`;   // TODO - Need to write the logic to update |h incase needed.


    let savePath = "";
    // Defining search and search manager
    var searchString = '| rest /servicesNS/-/uploader/configs/conf-uploader splunk_server=local | search "eai:acl.app"="uploader" | table *';
    var searchManager = new SearchManager({
        preview: true,
        autostart: true,
        search: searchString,
        cache: false
    });
    // Processing results search manager.
    var searchManagerResults = searchManager.data("results", {count: 0});
    searchManagerResults.on('data', function () {
        if (searchManagerResults.data()) {
            $.each(searchManagerResults.data().rows, function (index, row) {
                // TODO - Read for savepath and temppath here
            });
        }
    });

    underscore.templateSettings = {
      interpolate: /\{\{(.+?)\}\}/g
    };
    var fileItemTemplate = $('#fileTemplate').html(),
        fileTemplate = underscore.template(fileItemTemplate),
        fileList = $('.uploadingFiles'),
        btnPauseAll = $('.btnPauseAll'),
        btnCancelAll = $('.btnStopAll'),
        btnDeleteAll = $('.btnDeleteAll'),
        btnPurgePending = $('.btnPurgePending'),
        finishedList = $('.finishedFiles'),
        pendingList = $('.pendingFiles'),
        fileProgressStates = {},
        paused = false,
        statusUrl = Splunk.util.make_url('custom','uploader','upload'),
        managerIndexLink = '/manager/uploader/data/inputs/monitor/_new' +
        '?action=edit&redirect_override_cancel=%2Fmanager%2Fuploader%2Fdatainputstats&def.spl-ctrl_sourcetypeSelect=auto&def.spl-ctrl_switcher=oneshot&def.spl-ctrl_EnableAdvanced=1&app_only=False&preflight=preview&def.name='

    var updateSize = underscore.debounce(function(){
        $('.uploading-wrapper').find('.totalSize').text(humanFileSize(r.getSize()));
    },500);

    var updateServerFileList = underscore.debounce(function(){
        $.ajax('/custom/uploader/service/list').done(function(files){
            finishedList.empty();
            pendingList.empty();
            var size = [0,0];
            $.each(files, function(i, file){
                var fileElm = $(fileTemplate({
                    size: humanFileSize(file.size),
                    name: file.name
                }));

                if(file.finished){
                    size[0] = size[0]+file.size;
                    finishedList.append(fileElm);

                    // TODO - Check for correct value if savePath
                    var path = savePath + '/' + file.name;
                    var link = managerIndexLink + encodeURIComponent(path);
                    fileElm.append('<div class="indexLink"><a href="'+link+'" target="_new">Index this file in Splunk...</a></div>');
                }else{
                    size[1] = size[1]+file.size;
                    pendingList.append(fileElm);
                }

                fileElm.data('filename', file.name);
            });
            $('.uploaded-wrapper').find('.totalSize').text(humanFileSize(size[0]));
            $('.pending-wrapper').find('.totalSize').text(humanFileSize(size[1]));
        });
    }, 500);

    var r = new Resumable({
        target: statusUrl,
        query: {'splunk_form_key':formkey},
        chunkSize: 5*1024*1024
    });

    if(!r.support){
        alert("Your browser does not support Uploader! app.\n\nBefore you continue, please download a more sensible browser.");
        return;
    }

    updateServerFileList();

    r.assignBrowse($('#filetarget'));
    r.assignDrop($('#filetarget'));

    r.on('fileAdded', function(file){
        file.elm = $(fileTemplate({
            size: humanFileSize(file.size),
            name: file.fileName
        }));
        fileList.append(file.elm);

        //TODO move these event bindings up the dom/delegate
        var abortBtn = file.elm.find('.btnAbort');
        abortBtn.on('click', function(){
            file.cancel();
            file.elm.remove();
            delete file.elm;
            updateSize();
            updateServerFileList();
        });

        var retryBtn = file.elm.find('.btnRetry');
        retryBtn.on('click', function(){
            file.retry();
            file.elm.removeClass('uploaderror');
            file.elm.find('.message').text('');
            file.elm.find('.btnRetry').hide();
        });

        if(!paused){
            r.upload();
        }

        updateSize();
    });

    r.on('fileProgress', function(file){
        if(file.isComplete()){
            return;
        }

        var progress = file.progress();
        var now = (new Date()).getTime();

        var state = fileProgressStates[file.uniqueIdentifier];
        if(!state){
            state = fileProgressStates[file.uniqueIdentifier] = [now, progress];
        }

        var delta = (now - state[0]) / 1000;
        var transffered = file.size * (progress - state[1]);
        var rate = transffered / delta;
        //var left = r.getSize()-(file.size*progress);

        file.elm.find('.speed').text(humanFileSize(rate)+'/s');
        file.elm.find('.progress').css({width: Math.round(progress*100)+'%'});
        file.elm.addClass('uploading');

        if(delta > 10){
            fileProgressStates[file.uniqueIdentifier] = null;
        }
    });

    r.on('fileSuccess', function(file, message){
        console.log('file success', file);
        window.setTimeout(function(){
            file.elm.hide('slow', function(){
                file.elm.remove();
                file.elm='';
                file.cancel();
            });
        }, 900);

        //TODO report actual time taken/speed
        updateServerFileList();

    });

    r.on('fileError', function(file, message){
        try{
            message = JSON.parse(message);
        }catch(e){}

        if(message.errorcode>0 && message.message){
            file.elm.find('.message').text('Upload Failed. '+ message.message);
        }else{
            file.elm.find('.message').text('Upload Failed. Check web_service.log for error details.');
        }

        file.elm.find('.btnRetry').show();
        file.elm.addClass('uploaderror');
        file.elm.removeClass('uploading');
        file.elm.find('.speed').text('');
        file.elm.find('.progress').css({width: '0%'});

        updateServerFileList();
    });

    btnPauseAll.on('click', function(){
        if(!paused){
            r.pause();
            btnPauseAll.addClass('active');
            paused = true;
        }else{
            btnPauseAll.removeClass('active');
            fileProgressStates = {};
            r.upload();
            paused = false;
        }
    });

    btnCancelAll.on('click', function(){
        fileList.find('.file').each(function(i, elm){
            elm.remove();
        });
        r.cancel();
        updateSize();
        updateServerFileList();
    });

    btnPurgePending.on('click', function(){
        if(confirm('Are you sure you want to\nDELETE ALL PENDING UPLOADS on the server?')){
            $.ajax('/custom/uploader/service/removepending').done(function(){
                updateServerFileList();
            }).error(function(){
                alert('There was an error while deleting. Check web_service.log for more info.');
            });
        }
    });

    btnDeleteAll.on('click', function(){
        if(confirm('Are you sure you want to\nDELETE ALL UPLOADED FILES on the server?')){
            $.ajax('/custom/uploader/service/removeall').done(function(){
                updateServerFileList();
            }).error(function(){
                alert('There was an error while deleting. Check web_service.log for more info.');
            });
        }
    });

    finishedList.on('click', '.btnAbort', function(event){
        var target = $(event.target);
        var fileElm = target.closest('.file');
        var fileName = fileElm.data('filename');

        if(confirm('Are you sure you want to delete '+ fileName)){
            $.ajax('/custom/uploader/service/remove/'+ fileName).done(function(){
                fileElm.remove();
            }).error(function(){
                alert('There was an error while deleting. Check web_service.log for more info.');
            });
        }
    });

    //as found in http://stackoverflow.com/a/14919494
    function humanFileSize(bytes, si) {
        var thresh = si ? 1000 : 1024;
        if(bytes < thresh) return bytes + ' B';
        var units = si ? ['kB','MB','GB','TB','PB','EB','ZB','YB'] : ['KiB','MiB','GiB','TiB','PiB','EiB','ZiB','YiB'];
        var u = -1;
        do {
            bytes /= thresh;
            ++u;
        } while(bytes >= thresh);
        return bytes.toFixed(1)+' '+units[u];
    }

});