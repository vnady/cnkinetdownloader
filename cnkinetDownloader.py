#-*- coding=utf-8 -*-
import sys
import os
import urllib
import urllib2
import lxml.html
import logging
import cookielib
import re
from urlparse import urlparse

block_sz = 65536
g_retry = 8
site='http://www.cnki.net'
login_url = 'http://epub.cnki.net/kns/logindigital.aspx?ParentLocation=http://www.cnki.net'
xpath_4_filename = '//div[@class="wxTitle"]/h2[@class="title"]/text()'
xpath_4_downloadurl = '//div[@class="dllink"][@id="DownLoadParts"]/a[1]/@href'
UserAgent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36'
Headers = {'User-Agent': UserAgent}

#generating download_urls for papers in input file.
def gen_urls(inputfile=None, opener=None):
    if not all((inputfile, opener)):
        return []

    download_urls = []
    with open(inputfile,'r') as f:
        content = f.readlines()
    for line_url in content:
        line_url = line_url.strip()
        request = urllib2.Request(line_url)
        try:
            response = opener.open(request)
        except Exception as e:
            logging.error(e)
            try:
                response.close()
            except:
                pass
            continue

        page_doc = lxml.html.document_fromstring(response.read())
        page_doc.make_links_absolute(site)
        try:
            wxTitle = page_doc.xpath(xpath_4_filename)[0]
            url = page_doc.xpath(xpath_4_downloadurl)[0]
        except Exception as e:
            logging.error(e)
            del page_doc
            response.close()
            continue
        else:
            download_urls.append([wxTitle,url,line_url])
            print 'Generating paper: %s' % (wxTitle)
            response.close()
    return download_urls

#downloading papers in download_urls
def downloader(download_urls, save_path, opener=None):
    cnt=0
    if len(download_urls) is 0 or opener is None:
        return cnt

    for filename,req_url,referer in download_urls:
        try:
            Headers['Referer'] = 'http://'+urlparse(referer).hostname+'/'
            req = urllib2.Request(req_url,headers=Headers)
            r = opener.open(req)
            url = req_url
            i = 0
            while url != r.geturl():
                if i == g_retry:
                    break
                url = r.geturl()
                r.close()
                if re.search(r'?ReturnUrl=',url):
                    url = re.search(r'=.*$',url).group(0)[1:]
                    url = urllib.unquote_plus(url)
                r = opener.open(urllib2.Request(url,headers=Headers))
                i += 1

            if i == g_retry:
                print 'After %d times retry, downloading failed!' % (g_retry)
                continue
            file_size = int(r.info().getheaders("Content-Length")[0])
        except urllib2.HTTPError as e:
            logging.error(e)
            if e.code == 503:
                print 'Rest for a few minutes and try again!'
            try:
                r.close()
            except:
                pass
            continue

        except Exception as e:
            logging.error(e)
            #print 'Original_req_url: ',req_url
            #print 'Return_rep_url  : ',tmp_url
            #print 'Last_rep_url    : ',url
            #print Headers['Referer']
            try:
                r.close()
            except:
                pass
            continue

        print "Downloading: %s Bytes: %10d" % (filename, file_size)
        with open(save_path+'/'+filename+'.'+'caj','wb') as fp:
            file_size_dl = 0
            while True:
                buf = r.read(block_sz)
                if not buf:
                    break
                fp.write(buf)
                file_size_dl += len(buf)
                del buf

                #status bar
                status = r"%10d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100. / file_size)
                status = status + chr(8)*(len(status)+1)
                sys.stdout.write(status + '\r')
                sys.stdout.flush()
            r.close()
            fp.close()
	    cnt += 1

	return cnt

if  __name__ == '__main__':
    paperlist = sys.argv[1]

    # 1. Prapering dir
    PathToSave = '/Users/jiangtao/Downloads/cnkinetpapers'
    if not os.path.exists(PathToSave):
        with os.mkdir(PathToSave):
            if not os.path.exists(PathToSave):
                PathToSave = './cnkinetpapers'
                with os.mkdir(PathToSave):
                    if not os.path.exists(PathToSave):
                        logging.error('mkdir failed: '+PathToSave)
                        sys.exit(0)
    # 2. Prapering connect handle--request opener
    cookie = cookielib.CookieJar()
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie), urllib2.HTTPHandler)

    # 3. Login ...
    post_data = {
            'username': '',
            'password': '',
            'iplogin': ''}
    post_data  = urllib.urlencode(post_data)
    Headers['Referer'] = site
    request = urllib2.Request(url=login_url, data=post_data, headers=Headers)
    resp = opener.open(request)
    resp.close()

    # 4. Parser download_urls from detail-web-page links that save in paperlist
    Download_urls = gen_urls(paperlist, opener=opener)

    # 5. Downloader download all papers in Download_urls
    count = downloader(Download_urls, PathToSave, opener=opener)

    print "Finished downloading papers: %d\nSave to %s" % (count, PathToSave)
