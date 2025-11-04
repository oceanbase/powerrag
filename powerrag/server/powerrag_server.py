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

"""
PowerRAG Backend Server

This is a standalone backend service running on port 6000.
It provides APIs for document parsing, conversion, splitting, and extraction.
It reuses RAGFlow's data models and database tables.
"""

import os
import sys
import logging
import signal
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from werkzeug.serving import run_simple

# Initialize logging
from api.utils.log_utils import init_root_logger
init_root_logger("powerrag_server")

logger = logging.getLogger(__name__)

# Import after path is set
from api import settings
from api.db.db_models import init_database_tables as init_web_db
from api.db.runtime_config import RuntimeConfig
from powerrag.server.app import create_app


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Received interrupt signal, shutting down PowerRAG server...")
    sys.exit(0)


def main():
    """Main entry point for PowerRAG server"""
    
    logger.info(r"""
    ____                        ____  ___   ______
   / __ \____ _      _____  _____/ __ \/   | / ____/
  / /_/ / __ \ | /| / / _ \/ ___/ /_/ / /| |/ / __  
 / ____/ /_/ / |/ |/ /  __/ /  / _, _/ ___ / /_/ /  
/_/    \____/|__/|__/\___/_/  /_/ |_/_/  |_\____/   
                                                     
    PowerRAG Backend Service - Port 6000
    """)
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="PowerRAG Backend Server")
    parser.add_argument(
        "--port", 
        type=int, 
        default=6000, 
        help="Port to run the server on (default: 6000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode (enables debugger but not auto-reloader)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reloader (restarts server on file changes)"
    )
    args = parser.parse_args()
    
    logger.info(f"PowerRAG Server starting on {args.host}:{args.port}")
    
    # Initialize settings
    settings.init_settings()
    
    # Initialize database (reuse RAGFlow's database)
    logger.info("Initializing database connection (reusing RAGFlow database)...")
    init_web_db()
    
    # Initialize runtime config
    RuntimeConfig.DEBUG = args.debug
    if RuntimeConfig.DEBUG:
        logger.info("Running in debug mode")
    if args.reload:
        logger.info("Auto-reloader enabled (server will restart on file changes)")
    
    RuntimeConfig.init_env()
    RuntimeConfig.init_config(JOB_SERVER_HOST=args.host, HTTP_PORT=args.port)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create Flask app
    app = create_app()
    
    # Start server
    try:
        logger.info(f"PowerRAG server starting on http://{args.host}:{args.port}")
        logger.info("Available endpoints:")
        logger.info(f"  - POST http://{args.host}:{args.port}/api/v1/powerrag/parse")
        logger.info(f"  - POST http://{args.host}:{args.port}/api/v1/powerrag/convert")
        logger.info(f"  - POST http://{args.host}:{args.port}/api/v1/powerrag/split")
        logger.info(f"  - POST http://{args.host}:{args.port}/api/v1/powerrag/extract")
        logger.info(f"  - GET  http://{args.host}:{args.port}/health")
        
        run_simple(
            hostname=args.host,
            port=args.port,
            application=app,
            threaded=True,
            use_reloader=args.reload,  # Only reload if explicitly requested
            use_debugger=args.debug,   # Debugger enabled with --debug
        )
    except Exception as e:
        logger.error(f"Failed to start PowerRAG server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()




