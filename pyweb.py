import urllib2

address = 'http://localhost/tsweb/axsystem'
website = urllib2.urlopen(address)
website_html = website.read()

for line in website_html.split('\n') :
    line =  line.lstrip().split(' ')
    if '<ipaddr>' ==  line[0] :
        print 'ipaddr =',line[1]
    if '<sipport>' ==  line[0] :
        print 'sipport =',line[1]
