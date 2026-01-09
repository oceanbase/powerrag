#
#  Copyright 2025 The OceanBase Authors. All Rights Reserved.
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

import pytest
import time
from powerrag.sdk import PowerRAGClient


class TestRAPTORBuild:
    """测试RAPTOR构建"""
    
    def test_build_raptor(self, client: PowerRAGClient, kb_with_docs: str):
        """测试构建RAPTOR"""
        task_info = client.raptor.build(kb_with_docs)
        assert "raptor_task_id" in task_info
    
    def test_build_raptor_already_running(self, client: PowerRAGClient, kb_with_docs: str):
        """测试构建RAPTOR时任务已在运行"""
        # 先启动一个任务
        client.raptor.build(kb_with_docs)
        
        # 再次启动可能会失败或返回已有任务
        try:
            task_info = client.raptor.build(kb_with_docs)
            # 如果成功，说明系统允许重复构建
            assert "raptor_task_id" in task_info
        except Exception as e:
            # 如果失败，应该是因为任务已在运行
            assert "already running" in str(e).lower() or "running" in str(e).lower()


class TestRAPTORStatus:
    """测试RAPTOR状态查询"""
    
    def test_get_status(self, client: PowerRAGClient, kb_with_docs: str):
        """测试获取RAPTOR状态"""
        # 先构建
        task_info = client.raptor.build(kb_with_docs)
        
        # 查询状态
        status = client.raptor.get_status(kb_with_docs)
        assert status is not None
        assert "progress" in status
    
    def test_get_status_not_exists(self, client: PowerRAGClient, kb_with_docs: str):
        """测试获取不存在的RAPTOR状态"""
        # 确保没有运行的任务 - 只有在存在时才删除
        try:
            if client.raptor.get_status(kb_with_docs) is not None:
                client.raptor.delete(kb_with_docs)
        except Exception:
            pass
        
        status = client.raptor.get_status(kb_with_docs)
        assert status is None

