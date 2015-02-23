#! /usr/bin/env python
import sys
sys.path.insert(0, '/data/project/whois/local/lib/python2.7/site-packages')

from ipwhois import IPWhois
import cgitb
import urllib2
import cgi
import json
import os

PROVIDERS = {
    'ARIN': lambda x: 'http://whois.arin.net/rest/ip/' + urllib2.quote(x),
    'RIPENCC': lambda x: 'https://apps.db.ripe.net/search/query.html?searchtext=%s#resultsAnchor' % urllib2.quote(x),
    'AFRINIC': lambda x: 'http://afrinic.net/cgi-bin/whois?searchtext=' + urllib2.quote(x),
    'APNIC': lambda x: 'http://wq.apnic.net/apnic-bin/whois.pl?searchtext=' + urllib2.quote(x),
    'LACNIC': lambda x: 'http://lacnic.net/cgi-bin/lacnic/whois?lg=EN&amp;query=' + urllib2.quote(x)
}

def order_keys(x):
    keys = dict((y,x) for (x,y) in enumerate([
        'asn_registry', 'asn_country_code', 'asn_date', 'query', 'asn_cidr', 'nets',
        'name', 'description', 'address', 'city', 'state', 'country', 'postal_code',
        'cidr', 'range', 'created', 'updated', 'handle', 'abuse_emails', 'tech_emails', 'misc_emails']))
    if keys.has_key(x):
        return '0_%04d' % keys[x]
    else:
        return '1_%s' % x

def format_new_lines(s):
    return s.replace('\n', '<br/>')

def format_table(dct, target):
    if isinstance(dct, list):
        return '\n'.join(format_table(x, target) for x in dct)
    ret = '<div class="table-responsive"><table class="table table-condensed"><tbody>'
    for (k,v) in sorted(dct.items(), key=lambda x: order_keys(x[0])):
          if v is None or len(v) == 0 or v == 'NA' or v == 'None':
              ret += '<tr class="text-muted"><th>%s</th><td>%s</td></tr>' % (k, v)
          elif isinstance(v, basestring):
              if k == 'asn_registry' and PROVIDERS.has_key(v.upper()):
                  ret += '<tr><th>%s</th><td><a href="%s"><span class="glyphicon glyphicon-link"></span>%s</a></td></tr>' % (k, PROVIDERS[v.upper()](target), v.upper())
              else:
                  ret += '<tr><th>%s</th><td class="text-">%s</td></tr>' % (k, format_new_lines(v))
          else:
              ret += '<tr><th>%s</th><td>%s</td></tr>' % (k, format_table(v, target))
    ret += '</tbody></table></div>'
    return ret
              
def format_result(result, target):
    return '<div class="panel panel-default">%s</div>' % format_table(result, target)

def lookup(ip):
    obj = IPWhois(ip)
    result = obj.lookup_rws()

    # hack for retriving AFRINIC data when provided via RIPE's RWS
    if 'NON-RIPE-NCC-MANAGED-ADDRESS-BLOCK' in [x.get('name') for x in result['nets']]:
        result = obj.lookup()

    return result

if __name__ == '__main__':
    SITE = '//tools.wmflabs.org/whois'
    cgitb.enable(display=0, logdir='/data/project/whois/logs')
    form = cgi.FieldStorage()
    ip = form.getfirst('ip', '')
    provider = form.getfirst('provider', '').upper()
    fmt = form.getfirst('format', 'html').lower()
    doLookup = form.getfirst('lookup', 'false').lower() != 'false'

    result = {}
    error = False
    if doLookup:
        try:
            result = lookup(ip)
        except Exception as e:
            result = {'error': repr(e)}
            error = True
    
    if PROVIDERS.has_key(provider):
        print 'Location: %s' % PROVIDERS[provider](ip)
        print ''
        exit()

    if fmt == 'json' and doLookup:
        print 'Content-type: text/plain'
        print ''
        print json.dumps(result)
        exit()
        
    print 'Content-type: text/html'
    print ''
    print '''<!DOCTYPE HTML>
<html lang="en">
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="/static/res/bootstrap/3.2.0/css/bootstrap.min.css">
<link rel="stylesheet" href="/static/res/bootstrap/3.2.0/css/bootstrap-theme.min.css">
<title>Whois Gateway</title>
<style type="text/css">

.el { display: flex; flex-direction: row; align-items: baseline; }
.el-ip { flex: 0 1?; max-width: 70%%; overflow: hidden; text-overflow: ellipsis; padding-right: .2em; }
.el-prov { flex: 1 8em; }

</style>
</head>
<body>
<div class="container">
<div class="row">
<div class="col-sm-5">
<header><h1>Whois Gateway</h1></header>
</div>
<div class="col-sm-7"><div class="alert alert-warning" role="alert">
<strong>This tool is experimental.</strong> The URL and functionalities might change.
</div></div>
</div>

<div class="row">
<div class="col-sm-9">
''' % {'site': SITE}
    print '''
<form action="%(site)s/gateway.py" role="form">
<input type="hidden" name="lookup" value="true"/>
<div class="row form-group %(error)s">
<div class="col-sm-10"><div class="input-group"><label class="input-group-addon" for="ipaddress-input">IP address</label><input type="text" name="ip" value="%(ip)s" id="ipaddress-input" class="form-control" %(af)s/></div></div>
<div class="col-sm-2"><input type="submit" value="Lookup" class="btn btn-default btn-block"/></div>
</div>
</form>
''' % ({'site': SITE, 'ip': ip, 'error': 'has-error' if error else '', 'af': 'autofocus onFocus="this.select();"' if not doLookup or error else ''})

    if doLookup:
        link = 'https://tools.wmflabs.org/whois/%s/lookup' % ip
        linkthis = 'Link this result: <a href="%s">%s</a>' % (link, link)
        print '<div class="panel panel-default"><div class="panel-body">%s</div><div class="panel-heading">%s</div></div>' % (format_table(result, ip), linkthis)
    
    print '''
</div>
<div class="col-sm-3">
<div class="panel panel-default">
<div class="panel-heading">External links</div>
<div class="list-group">
'''

    for (name,q) in sorted(PROVIDERS.items()):
        cls = 'list-group-item active' if result.get('asn_registry', '').upper() == name else 'list-group-item'
        print '<a class="el %s" href="%s" title="Look up %s at %s"><span class="el-ip">%s</span><small class="el-prov"> @%s</small></a>' % (cls, q(ip), ip, name, ip, name)
    print '</div>'

print '''
</div>
</div>
</div>

<footer><div class="container">
<hr>
<p class="text-center text-muted"><a href="https://tools.wmflabs.org/whois/">Whois Gateway</a> <small>(<a href="https://github.com/whym/whois-gateway">source code</a>, <a href="https://github.com/whym/whois-gateway#api">API</a>)</small> on <a href="https://tools.wmflabs.org">Tool Labs</a> / <a href="https://github.com/whym/whois-gateway/issues">Issues?</a></p></div></footer>
</div>
</body></html>''' % {'site': SITE}
