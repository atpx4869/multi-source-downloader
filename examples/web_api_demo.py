#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web API 示例 - 使用 Flask 包装 APIRouter

这个示例展示如何使用 Flask 为 APIRouter 提供 REST API 服务。
可以轻松扩展成完整的 Web 服务或与前端框架集成。
"""
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from flask import Flask, request, jsonify
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

from api import APIRouter, SourceType, DownloadStatus


def create_app():
    """创建 Flask 应用"""
    app = Flask(__name__)
    router = APIRouter()
    
    @app.route('/api/health', methods=['GET'])
    def health():
        """健康检查 - GET /api/health"""
        health_response = router.check_health()
        return jsonify(health_response.to_dict())
    
    @app.route('/api/search', methods=['GET'])
    def search():
        """搜索标准 - GET /api/search?source=ZBY&q=GB/T+3324&limit=10"""
        source_str = request.args.get('source', 'ZBY').upper()
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', '100'))
        
        try:
            source_type = SourceType[source_str]
            response = router.search_single(source_type, query, limit)
            return jsonify(response.to_dict())
        except KeyError:
            return jsonify({
                'error': f'Unknown source: {source_str}',
                'available_sources': [s.value for s in SourceType]
            }), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/search/all', methods=['GET'])
    def search_all():
        """在所有源中搜索 - GET /api/search/all?q=GB/T+3324&limit=10"""
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', '100'))
        
        try:
            results = router.search_all(query, limit)
            return jsonify({
                'query': query,
                'sources': {source.value: response.to_dict() for source, response in results.items()}
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/download', methods=['POST'])
    def download():
        """下载标准 - POST /api/download
        
        JSON 请求体:
        {
            "source": "ZBY",
            "std_no": "GB/T 3324-2024"
        }
        """
        data = request.get_json() or {}
        source_str = data.get('source', 'ZBY').upper()
        std_no = data.get('std_no', '')
        
        if not std_no:
            return jsonify({'error': 'std_no is required'}), 400
        
        try:
            source_type = SourceType[source_str]
            response = router.download(source_type, std_no)
            return jsonify(response.to_dict())
        except KeyError:
            return jsonify({
                'error': f'Unknown source: {source_str}',
                'available_sources': [s.value for s in SourceType]
            }), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/download/auto', methods=['POST'])
    def download_auto():
        """自动从可用源下载 - POST /api/download/auto
        
        JSON 请求体:
        {
            "std_no": "GB/T 3324-2024"
        }
        """
        data = request.get_json() or {}
        std_no = data.get('std_no', '')
        
        if not std_no:
            return jsonify({'error': 'std_no is required'}), 400
        
        try:
            response = router.download_first_available(std_no)
            return jsonify(response.to_dict())
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/sources', methods=['GET'])
    def sources():
        """获取可用源列表 - GET /api/sources"""
        enabled = router.get_enabled_sources()
        return jsonify({
            'sources': [s.value for s in enabled],
            'count': len(enabled)
        })
    
    return app


def main():
    """主函数"""
    if not HAS_FLASK:
        print("❌ Flask 未安装。请运行:")
        print("   pip install flask")
        print("\n或使用 API 模块的内置接口:")
        print("   python -c 'from api import APIRouter; router = APIRouter(); print(router)'")
        return
    
    print("\n" + "="*60)
    print("🚀 Web API 示例服务器")
    print("="*60)
    print("\n正在启动 Flask 开发服务器...")
    print("访问 http://localhost:5000 进行 API 调用\n")
    
    app = create_app()
    
    # API 文档
    print("📚 API 端点列表:")
    print("  GET  /api/health                  - 健康检查")
    print("  GET  /api/sources                 - 可用源列表")
    print("  GET  /api/search                  - 在指定源中搜索")
    print("  GET  /api/search/all              - 在所有源中搜索")
    print("  POST /api/download                - 从指定源下载")
    print("  POST /api/download/auto           - 自动从可用源下载")
    
    print("\n📝 使用示例:")
    print("  curl 'http://localhost:5000/api/health'")
    print("  curl 'http://localhost:5000/api/search?source=ZBY&q=GB/T+3324'")
    print("  curl -X POST http://localhost:5000/api/download -H 'Content-Type: application/json' \\")
    print("    -d '{\"source\":\"ZBY\",\"std_no\":\"GB/T 3324-2024\"}'")
    print("\n" + "="*60 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)


if __name__ == '__main__':
    main()
