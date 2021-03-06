import os
from subprocess import Popen, PIPE
from datetime import date, datetime
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth.decorators import user_passes_test
from django.contrib.admin.views.decorators import staff_member_required

from django.core import serializers
from django.core.exceptions import ImproperlyConfigured
from django.core.management.commands.dumpdata import sort_dependencies
from django.db import router, DEFAULT_DB_ALIAS
from django.db.models import get_apps, get_app

from django.shortcuts import render_to_response
from django.utils.datastructures import SortedDict
from django.template.context import RequestContext
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

BACKUP_DIR = getattr(settings, 'BACKUP_DIR', os.path.join(settings.MEDIA_ROOT, 'backup'))

@staff_member_required
def backup_database(request):

    if request.method == 'POST':

        output = Popen(['which', 'mysqldump'], stdout=PIPE, close_fds=True).communicate()[0]

        mysqldump_bin = output.replace('\n','')

        cmd = mysqldump_bin+' -h %s --opt --compact --skip-add-locks -u %s -p%s %s' % \
                    (getattr(settings.DATABASES['default'], 'HOST', 'localhost'),
                     settings.DATABASES['default']['USER'],
                     settings.DATABASES['default']['PASSWORD'],
                     settings.DATABASES['default']['NAME'])

        pop1 = Popen(cmd.split(" "), stdout=PIPE, close_fds=True)
        pop2 = Popen(["bzip2", "-c"], stdin=pop1.stdout, stdout=PIPE, close_fds=True)
        output = pop2.communicate()[0]
        
        default_storage.save(BACKUP_DIR+"/"+datetime.today().strftime("%Y-%m-%d_%H:%M:%S")+"_db.sql.bz2", ContentFile(output))
    
    files = default_storage.listdir(BACKUP_DIR)[1]
    files.sort(reverse=True)
    return render_to_response('diagnostic/backupdb.html', 
                                {'files':files,}, 
                                context_instance=RequestContext(request))

@staff_member_required
def export_database(request):
    output = Popen(['which', 'mysqldump'], stdout=PIPE, close_fds=True).communicate()[0]

    mysqldump_bin = output.replace('\n','')

    cmd = mysqldump_bin+' -h %s --opt --compact --skip-add-locks -u %s -p%s %s' % \
                (getattr(settings.DATABASES['default'], 'HOST', 'localhost'),
                 settings.DATABASES['default']['USER'],
                 settings.DATABASES['default']['PASSWORD'],
                 settings.DATABASES['default']['NAME'])

    pop1 = Popen(cmd.split(" "), stdout=PIPE, close_fds=True)
    pop2 = Popen(["bzip2", "-c"], stdin=pop1.stdout, stdout=PIPE, close_fds=True)
    output = pop2.communicate()[0]
    
    response = HttpResponse(output, mimetype="application/octet-stream")
    response['Content-Disposition'] = 'attachment; filename=%s' % date.today().__str__()+'_db.sql.bz2'
    return response

@staff_member_required
def dump_data(request,appname):
    app_list = SortedDict()
    
    try:
        if request.method == 'POST':
            for appname in request.POST.getlist('apps'):
                app = get_app(appname)
                app_list[app] = None
            appname = 'choices'
        else:
            app = get_app(appname)
            app_list[app] = None
    except ImproperlyConfigured:
        if appname == 'all':
            for app in get_apps():
                app_list[app] = None

    if(len(app_list) > 0):
        objects = []
        for model in sort_dependencies(app_list.items()):
            if not model._meta.proxy and router.allow_syncdb(DEFAULT_DB_ALIAS, model):
                objects.extend(model._default_manager.using(DEFAULT_DB_ALIAS).all())
        serializers.get_serializer('json')
        json = serializers.serialize('json', objects, indent=2,use_natural_keys=True)
        response = HttpResponse(json, mimetype='application/json');
        response['Content-Disposition'] = 'attachment; filename=%s_%s_fixture.json' % (date.today().__str__(),appname)
        return response

    return render_to_response('diagnostic/dumpdata.html',context_instance=RequestContext(request))

def smoke_test(request):
    from datetime import datetime
    return HttpResponse(datetime.now().strftime('%H:%M:%S'))

@user_passes_test(lambda u: u.is_staff)
def req_dump(request):
    template = '''
    <form action="./" method="POST">
    <input type="text" name="word" value="mitochondrial">
    <input type="submit" name="btn1" value="one">
    <input type="submit" name="btn2" value="two">
    </form>
    <table border="1">
       <tr><th>key</th><th>POST[key]</th></tr>
    %s
    </table>
    <hr>
    <p>
      <a href="this_is_a_broken_link">Click to test broken link notification</a>
    </p>
    '''
    rows = []
    for k in request.POST.keys():
        rows.append('<tr><th>%s</th><td>%s</td></tr>' % (k, request.POST[k]))
    return HttpResponse(template % ('\n'.join(rows)))

@user_passes_test(lambda u: u.is_staff)
def sys_info(request):
    template = u'''
    <h1>Revision</h1>
    %(svn_version)s
    <h1>settings path</h1>
    <pre>%(settingspath)s</pre>
    <h1>Site.objects.get_current()</h1>
    <table>
       <tr><th>id</th><td>%(site.pk)s</td></tr>
       <tr><th>domain</th><td>%(site.domain)s</td></tr>
       <tr><th>name</th><td>%(site.name)s</td></tr>
    </table>
    <h1>svn info</h1>
    <pre>%(svninfo)s</pre>
    <h1>sys.path</h1>
    <pre>%(syspath)s</pre>
    '''
    import sys
    import settings
    from django.contrib.sites.models import Site
    from subprocess import Popen, PIPE
    svn_version, svn_version_err = Popen(['svnversion', settings.PROJECT_PATH], stdout=PIPE).communicate()
    svn_version = svn_version.decode('utf-8') if svn_version else u''
    svn_version_err = svn_version_err.decode('utf-8') if svn_version_err else u''
    site = Site.objects.get_current()
    svnout, svnerr = Popen(['svn', 'info','--non-interactive','--username=anonymous','--password=4guests@','-r', 'HEAD', settings.PROJECT_PATH], stdout=PIPE).communicate()
    svnout = svnout.decode('utf-8') if svnout else u''
    svnerr = svnerr.decode('utf-8') if svnerr else u''
    return HttpResponse(template % {'site.pk':site.pk,
                                    'site.domain':site.domain,
                                    'site.name':site.name,
                                    'svn_version': svn_version + svn_version_err,
                                    'settingspath': settings.PROJECT_PATH,
                                    'syspath':'\n'.join(sys.path),
                                    'svninfo':svnout + svnerr})

@user_passes_test(lambda u: u.is_staff)
def raise_error(request):
    class FakeError(StandardError):
        ''' this is just to test error e-mails and logging '''
    raise FakeError('This is not really an error')



