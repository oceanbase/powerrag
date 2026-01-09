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

"""PowerRAG Quart Application Configuration"""

import logging
import json
from quart import Quart
from quart_cors import cors
from api.utils.json_encode import CustomJSONEncoder

logger = logging.getLogger(__name__)


def create_app():
    """Create and configure the PowerRAG Quart application"""
    
    app = Quart(__name__)
    
    # CORS configuration - allow requests from RAGFlow frontend
    # Note: Cannot use allow_credentials=True with wildcard allow_origin="*"
    # Since PowerRAG has its own API key authentication, we don't need credentials
    app = cors(app, allow_origin="*", allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    
    # Request configuration
    app.url_map.strict_slashes = False
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1GB max upload
    
    # Custom JSON encoder for Chinese characters
    @app.before_serving
    async def setup_json_encoder():
        """Setup custom JSON encoder"""
        import functools
        import json
        json.dumps = functools.partial(json.dumps, cls=CustomJSONEncoder, ensure_ascii=False)
    
    # Register blueprints
    from powerrag.server.routes.powerrag_routes import powerrag_bp
    from powerrag.server.routes.task_routes import task_bp
    
    app.register_blueprint(powerrag_bp, url_prefix="/api/v1/powerrag")
    app.register_blueprint(task_bp, url_prefix="/api/v1/powerrag")
    
    # Health check endpoint
    @app.route("/health", methods=["GET"])
    async def health_check():
        return {"status": "ok", "service": "powerrag"}, 200
    
    logger.info("PowerRAG Quart application created successfully")
    
    return app

