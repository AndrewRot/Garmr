from urlparse import urlparse
import requests
from scanner import ActiveTest, PassiveTest, HtmlTest, Scanner, get_url

class HttpOnlyAttributePresent(PassiveTest):
    description = "Inspect the Set-Cookie: header and determine if the HttpOnly attribute is present."
    def analyze(self, response):
        cookieheader = "Set-Cookie"
        has_cookie = cookieheader in response.headers
        if has_cookie:
            if "httponly" in response.headers[cookieheader].lower():
                result = self.result("Pass", "HttpOnly is set", response.headers[cookieheader])
            else:
                result = self.result("Fail", "HttpOnly is not set", response.headers[cookieheader])            
        else:
            result = self.result("Skip", "No cookie is set by this response.", None)
        return result
    
class SecureAttributePresent(PassiveTest):
    description = "Inspect the Set-Cookie: header and determine if the Secure attribute is present."
    def analyze(self, response):
        url = urlparse(response.url)
        cookieheader = "Set-Cookie"
        has_cookie = cookieheader in response.headers
        if has_cookie:
            if "httponly" in response.headers[cookieheader].lower():
                if url.scheme == "https":
                    result = self.result("Pass", "HttpOnly is set", response.headers[cookieheader])
                else:
                    result = self.result("Fail", "HttpOnly should only be set for cookies sent over SSL.", response.headers[cookieheader]) 
            else:
                if url.scheme == "https":
                    result = self.result("Fail", "HttpOnly is not set", response.headers[cookieheader])
                else:
                    result = self.result("Pass", "The secure attribute is not set (expected for HTTP)", response.headers[cookieheader])            
        else:
            result = self.result("Skip", "No cookie is set by this response.", None)
        return result
        

class StrictTransportSecurityPresent(PassiveTest):
    secure_only = True
    description = "Check if the Strict-Transport-Security header is present in TLS requests."
    def analyze(self, response):
        stsheader = "Strict-Transport-Security"
        sts = stsheader in response.headers
        if sts == False:
            result = self.result("Fail", "Strict-Transport-Security header not found.", None)
        else:
            result = self.result("Pass", "Strict-Transport-Security header present.", response.headers[stsheader])
        return result

class XFrameOptionsPresent(PassiveTest):
    description = "Check if X-Frame-Options header is present."
    def analyze(self, response):
        xfoheader = "X-Frame-Options"
        xfo = xfoheader in response.headers
        if xfo == False:
            result = self.result("Fail", "X-Frame-Options header not found.", None)
        else:
            result = self.result("Pass", "X-Frame-Options header present.", response.headers[xfoheader])
        return result

class Http200Check(ActiveTest):
    run_passives = True
    description = "Make a GET request to the specified URL, reporting success only on a 200 response without following redirects"
    def do_test(self, url):
        response = get_url(url, False)
        if response.status_code == 200:
            result = self.result("Pass", "The request returned an HTTP 200 response.", None)
        else:
            result = self.result("Fail", "The response code was %s" % response.status_code, None)
	return (result, response)

class WebTouch(ActiveTest):
     run_passives = True
     description = "Make a GET request to the specified URL, and check for a 200 response after resolving redirects."
     def do_test(self, url):
         response = requests.get(url)
         if response.status_code == 200:
             result = self.result("Pass", "The request returned an HTTP 200 response.", None)
         else:
             result = self.result("Fail", "The response code was %s" % response.status_code, None)
         return (result, response)
    
class StsUpgradeCheck(ActiveTest):
    insecure_only = True
    run_passives = False
    description = "Inspect the Strict-Transport-Security redirect process according to http://tools.ietf.org/html/draft-hodges-strict-transport-sec"
    
    def do_test(self, url):
        stsheader = "Strict-Transport-Security"
        u = urlparse(url)
        if u.scheme == "http":
            correct_header = False
            bad_redirect = False
            response1 = get_url(url, False)
            invalid_header = stsheader in response1.headers
            is_redirect = response1.status_code == 301
            if is_redirect == True:
                redirect = response1.headers["location"]
                r = urlparse(redirect)
                if r.scheme == "https":
                    response2 = get_url(redirect, False)
                    correct_header = stsheader in response2.headers
                else:
                    bad_redirect = True
                    
            success = invalid_header == False and is_redirect == True and correct_header == True
            if success == True:
                message = "The STS upgrade occurs properly (no STS header on HTTP, a 301 redirect, and an STS header in the subsequent request."
            else:
                message = "%s%s%s%s" % (
                    "The initial HTTP response included an STS header (RFC violation)." if invalid_header else "",
                    "" if is_redirect else "The initial HTTP response should be a 301 redirect (RFC violation see ).",
                    "" if correct_header else "The followup to the 301 redirect must include the STS header.",
                    "The 301 location must use the https scheme." if bad_redirect else ""
                    )
            result = self.result("Pass" if success else "Fail", message, None)
            return (result, response1)

class HttpsLoginForm(HtmlTest):
    description = "Check that html forms with password-type inputs point to https"
    def analyze_html(self, response, soup):
        url = urlparse(response.url)
        forms = soup.findAll('form')
        # look only at those form elements that have password type input elements as children
        forms = filter(lambda x: x.findChildren("input", type="password") ,forms)
        if len(forms) == 0:
            result = self.result("Skip", "There are no login forms on this page", None)
            return result
        failforms = []
        for form in forms:
            if url.scheme == "https":
                if form['action'].startswith('http:'):
                    failforms.append(form)
            else:
                if not form['action'].startswith('https'):
                    failforms.append(form)
        if len(failforms) == 0:
            result = self.result("Pass", "All login forms point to secure resources", forms)
        else:
            result = self.result("Fail", "There are login forms pointing to insecure locations", failforms)
        return result

def configure(scanner):
    if isinstance(scanner, Scanner) == False:
        raise Exception("Cannot configure a non-scanner object!")
    scanner.register_check(Http200Check())
    scanner.register_check(WebTouch())
    scanner.register_check(StrictTransportSecurityPresent())
    scanner.register_check(XFrameOptionsPresent())
    scanner.register_check(StsUpgradeCheck())
    scanner.register_check(HttpOnlyAttributePresent())
    scanner.register_check(SecureAttributePresent())
    scanner.register_check(HttpsLoginForm())
