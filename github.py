from datetime import datetime
import requests
import aiohttp
import asyncio
from bs4 import BeautifulSoup, Tag
from util import obj_to_string
from typing import Union

blame_pattern = "https://github.com/{repo}/blame/{sha}/{filepath}"

session: Union[aiohttp.ClientSession, None] = None


async def request(url) -> str:
    async with session.get(url) as res:
        return await res.text()


class Snapshot:
    @staticmethod
    async def from_repo_sha(repo: str, sha: str):
        data = requests.get('https://api.github.com/repos/{}/git/trees/{}?recursive=1'.format(repo, sha)).json()
        file_data = data['tree']
        baseurl = "https://github.com/{}/blame/{}/".format(repo, sha)
        urls = [baseurl + f['path'] for f in file_data]
        coros = map(File.from_url, urls)
        tasks, _ = await asyncio.wait(map(asyncio.create_task, coros))
        return Snapshot(repo, sha, [task.result() for task in tasks])

    def __init__(self, repo: str, sha: str, files: ['File']):
        self.repo = repo
        self.sha = sha
        self.files = files


class File:
    def __init__(self, url: str, blames: ['BlameHunk']):
        self.url = url
        self.blames = blames

    def __repr__(self):
        return obj_to_string(File, self)

    @staticmethod
    async def from_url(url: str) -> 'File':
        page = await request(url)
        soup = BeautifulSoup(page, "html.parser")
        blames = [BlameHunk.from_html(x) for x in soup.find_all(class_='blame-hunk')]
        return File(url, blames)


class Line:
    def __init__(self, line_number: int, content: str, is_comment: bool):
        self.line_number = line_number
        self.content = content
        self.is_comment = is_comment

    def __repr__(self):
        return obj_to_string(Line, self)

    @staticmethod
    def from_html(html: Tag) -> 'Line':
        line_number = int(html.find(class_='js-line-number').text)
        content = str(html.find(class_='blob-code'))
        # todo: handle things like `xxxxxx /*xxx*/ xxxx`
        is_comment = html.find(class_='pl-c') is not None
        return Line(line_number, content, is_comment)


class BlameHunk:
    def __init__(self, datetime_: datetime, lines: [Line]):
        self.datetime = datetime_
        self.lines = lines

    def __repr__(self):
        return obj_to_string(BlameHunk, self)

    @staticmethod
    def from_html(html: Tag) -> 'BlameHunk':
        # `[:-1]` means cut away the 'Z'
        datetime_ = datetime.fromisoformat(html.find(class_='blame-commit-date').find('time-ago')['datetime'][:-1])
        lines = list(map(Line.from_html, html.find(class_="width-full").find_all(class_='d-flex')))
        return BlameHunk(datetime_, lines)


async def main():
    global session
    session = aiohttp.ClientSession()
    snap = await Snapshot.from_repo_sha('tikv/tikv', '25862308221cb5f332b3761f0f090ace64db0bc3')
    await session.close()
    print(snap.files)


if __name__ == '__main__':
    asyncio.run(main())
