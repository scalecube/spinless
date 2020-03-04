import requests

class Github:

    def __init__(self, github_gateway):
        self.github_gateway = github_gateway

    def createComment(self, jsonData):
        uri = self.github_gateway + "comment/{}/{}/{}/".format(jsonData["owner"], jsonData["repo"],
                                                               jsonData["issue_number"])
        # sending post request and saving response as response object
        r = requests.post(uri, json=jsonData)
        return r.text

    def chekcUpdate(self, jsonData):
        uri = self.github_gateway + "checks/status/{}/{}/{}/".format(jsonData["owner"], jsonData["repo"],
                                                                     jsonData["sha"])
        # sending post request and saving response as response object
        r = requests.post(uri, json=jsonData)
        print('###### RESPONSE: #######\n', r, r.text, 'URI: ', uri, 'data: ', jsonData)
        return r.text