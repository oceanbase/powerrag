#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
from datetime import datetime

from common.constants import FileSource
from api.db.db_models import DB
from api.db.db_models import File, File2Document
from api.db.services.common_service import CommonService
from api.db.services.document_service import DocumentService
from common.time_utils import current_timestamp, datetime_format


class File2DocumentService(CommonService):
    model = File2Document

    @classmethod
    @DB.connection_context()
    def get_by_file_id(cls, file_id):
        objs = cls.model.select().where(cls.model.file_id == file_id)
        return objs

    @classmethod
    @DB.connection_context()
    def get_by_document_id(cls, document_id):
        objs = cls.model.select().where(cls.model.document_id == document_id)
        return objs

    @classmethod
    @DB.connection_context()
    def get_by_document_ids(cls, document_ids):
        objs = cls.model.select().where(cls.model.document_id.in_(document_ids))
        return list(objs.dicts())

    @classmethod
    @DB.connection_context()
    def insert(cls, obj):
        if not cls.save(**obj):
            raise RuntimeError("Database error (File)!")
        return File2Document(**obj)

    @classmethod
    @DB.connection_context()
    def delete_by_file_id(cls, file_id):
        return cls.model.delete().where(cls.model.file_id == file_id).execute()

    @classmethod
    @DB.connection_context()
    def delete_by_document_ids_or_file_ids(cls, document_ids, file_ids):
        if not document_ids:
            return cls.model.delete().where(cls.model.file_id.in_(file_ids)).execute()
        elif not file_ids:
            return cls.model.delete().where(cls.model.document_id.in_(document_ids)).execute()
        return cls.model.delete().where(cls.model.document_id.in_(document_ids) | cls.model.file_id.in_(file_ids)).execute()

    @classmethod
    @DB.connection_context()
    def delete_by_document_id(cls, doc_id):
        return cls.model.delete().where(cls.model.document_id == doc_id).execute()

    @classmethod
    @DB.connection_context()
    def update_by_file_id(cls, file_id, obj):
        obj["update_time"] = current_timestamp()
        obj["update_date"] = datetime_format(datetime.now())
        cls.model.update(obj).where(cls.model.id == file_id).execute()
        return File2Document(**obj)

    @classmethod
    @DB.connection_context()
    def get_storage_address(cls, doc_id=None, file_id=None):
        if doc_id:
            f2d = cls.get_by_document_id(doc_id)
        else:
            f2d = cls.get_by_file_id(file_id)
        if f2d:
            file = File.get_by_id(f2d[0].file_id)
            if not file.source_type or file.source_type == FileSource.LOCAL:
                return file.parent_id, file.location
            doc_id = f2d[0].document_id

        assert doc_id, "please specify doc_id"
        e, doc = DocumentService.get_by_id(doc_id)
        return doc.kb_id, doc.location

    @classmethod
    @DB.connection_context()
    def get_storage_addresses(cls, doc_ids):
        """Batch get storage addresses for multiple documents.
        
        Args:
            doc_ids: List of document IDs
            
        Returns:
            dict: Mapping of doc_id to (bucket, name) tuple
        """
        if not doc_ids:
            return {}
        
        # Batch query file2document relationships
        f2d_list = cls.model.select().where(cls.model.document_id.in_(doc_ids))
        f2d_dict = {f2d.document_id: f2d for f2d in f2d_list}
        
        # Get file_ids for local files
        file_ids = [f2d.file_id for f2d in f2d_list]
        files_dict = {}
        if file_ids:
            files = File.select().where(File.id.in_(file_ids))
            files_dict = {f.id: f for f in files}
        
        # Collect doc_ids that need to query document table
        fallback_doc_ids = []
        result = {}
        
        for doc_id in doc_ids:
            if doc_id in f2d_dict:
                f2d = f2d_dict[doc_id]
                file = files_dict.get(f2d.file_id)
                if file and (not file.source_type or file.source_type == FileSource.LOCAL):
                    result[doc_id] = (file.parent_id, file.location)
                    continue
            fallback_doc_ids.append(doc_id)
        
        # Batch query documents for non-local files
        if fallback_doc_ids:
            from api.db.db_models import Document
            docs = Document.select().where(Document.id.in_(fallback_doc_ids))
            for doc in docs:
                result[doc.id] = (doc.kb_id, doc.location)
        
        return result