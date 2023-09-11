#!/usr/bin/env python3
from os import path as ospath, walk
from aiofiles.os import path as aiopath
from asyncio import sleep
from aiohttp import ClientSession

from bot import LOGGER
from bot.helper.ext_utils.bot_utils import is_gofile_token, sync_to_async

class Gofile:
    def __init__(self, dluploader=None, token=None):
        self.api_url = "https://api.gofile.io/"
        self.dluploader = dluploader
        self.token = token
        if self.token is not None:
            is_gofile_token(url=self.api_url, token=self.token)

    async def __resp_handler(self, response):
        api_resp = response.get("status", "")
        if api_resp == "ok":
            return response["data"]
        raise Exception(api_resp.split("-")[1] if "error-" in api_resp else "Response Status is not ok and Reason is Unknown")

    async def __getServer(self):
        async with ClientSession() as session:
            async with session.get(f"{self.api_url}getServer") as resp:
                return await self.__resp_handler(await resp.json())

    async def __getAccount(self, check_account=False):
        if self.token is None:
            raise Exception()
        
        api_url = f"{self.api_url}getAccountDetails?token={self.token}&allDetails=true"
        async with ClientSession() as session:
            resp = await (await session.get(url=api_url)).json()
            if check_account:
                return resp["status"] == "ok" if True else await self.__resp_handler(resp)
            else:
                return await self.__resp_handler(resp)
        
    async def upload_folder(self, folder_path, parent_folder_id=None):
        if not os.path.exists(folder_path):
            raise Exception("Folder does not exist")

        folder_name = os.path.basename(folder_path)
        folder_data = self.create_folder(parent_folder_id, folder_name)

        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path):
                await self.upload_file(item_path, folder_data["id"])
            elif os.path.isdir(item_path):
                await self.upload_folder(item_path, folder_data["id"])

        # Set the first folder's link to public
        if folder_data["code"]:
            await self.set_option(folder_data["id"], "public", "true")
        LOGGER.info(folder_data["code"])
        return folder_data["code"]


    async def upload_file(self, file: str, folderId: str = "", description: str = "", password: str = "", tags: str = "", expire: str = ""):
        if password and len(password) < 4:
            raise ValueError("Password Length must be greater than 4")

        server = (await self.__getServer())["server"]
        token = self.token if self.token else ""
        req_dict = {}
        if token:
            req_dict["token"] = token
        if folderId:
            req_dict["folderId"] = folderId
        if description:
            req_dict["description"] = description
        if password:
            req_dict["password"] = password
        if tags:
            req_dict["tags"] = tags
        if expire:
            req_dict["expire"] = expire
        
        if self.dluploader.is_cancelled:
            return
        self.dluploader.last_uploaded = 0
        upload_file = await self.dluploader.upload_aiohttp(f"https://{server}.gofile.io/uploadFile", file, "file", req_dict)
        return await self.__resp_handler(upload_file)
        
    async def upload(self, file_path):
        if await aiopath.isfile(file_path):
            cmd = await self.upload_file(file=file_path)
            if cmd and 'downloadPage' in cmd:
                return cmd['downloadPage']
        elif await aiopath.isdir(file_path):
            cmd = await self.upload_folder(path=file_path)
            if cmd:
                folderurl = f"https://gofile.io/d{cmd}"
                return folderurl
        raise Exception("Failed to upload file/folder to Gofile API, Retry or Try after sometimes...")

    async def create_folder(self, parentFolderId, folderName):
        if self.token is None:
            raise Exception()
        
        async with ClientSession() as session:
            async with session.put(url=f"{self.api_url}createFolder",
                data={
                        "parentFolderId": parentFolderId,
                        "folderName": folderName,
                        "token": self.token
                    }
                ) as resp:
                return await self.__resp_handler(await resp.json())

    async def __setOptions(self, contentId, option, value):
        if self.token is None:
            raise Exception()
        
        if not option in ["public", "password", "description", "expire", "tags"]:
            raise Exception(f"Invalid GoFile Option Specified : {option}")
        async with ClientSession() as session:
            async with session.put(url=f"{self.api_url}setOption",
                data={
                        "token": self.token,
                        "contentId": contentId,
                        "option": option,
                        "value": value
                    }
                ) as resp:
                return await self.__resp_handler(await resp.json())

    async def get_content(self, contentId):
        if self.token is None:
            raise Exception()
        
        async with ClientSession() as session:
            async with session.get(url=f"{self.api_url}getContent?contentId={contentId}&token={self.token}") as resp:
                return await self.__resp_handler(await resp.json())

    async def copy_content(self, contentsId, folderIdDest):
        if self.token is None:
            raise Exception()
        async with ClientSession() as session:
            async with session.put(url=f"{self.api_url}copyContent",
                    data={
                        "token": self.token,
                        "contentsId": contentsId,
                        "folderIdDest": folderIdDest
                    }
                ) as resp:
                return await self.__resp_handler(await resp.json())

    async def delete_content(self, contentId):
        if self.token is None:
            raise Exception()
        async with ClientSession() as session:
            async with session.delete(url=f"{self.api_url}deleteContent",
                    data={
                        "contentId": contentId,
                        "token": self.token
                    }
                ) as resp:
                return await self.__resp_handler(await resp.json())
