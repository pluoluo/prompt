import json
import unittest
from unittest.mock import patch, AsyncMock

import httpx
from backend import matching


class TextProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_compatible_provider_uses_final_answer_not_reasoning(self):
        def respond(request):
            payload = json.loads(request.content)
            self.assertEqual(payload['model'], 'deepseek-flash')
            self.assertEqual(payload['messages'][0]['role'], 'system')
            self.assertEqual(request.headers['Authorization'], 'Bearer test-only')
            return httpx.Response(200, json={'choices': [{'message': {
                'reasoning_content': 'private reasoning', 'content': '{"optimized_prompt":"wood chair"}'
            }}]})
        with patch.object(matching, '_text_config', return_value=('test-only', 'https://test.invalid/v1/chat/completions', 'deepseek-flash')):
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                answer = await matching._chat_content(client, 'system', [{'role':'user', 'content':'chair'}])
        self.assertEqual(json.loads(answer)['optimized_prompt'], 'wood chair')
        self.assertNotIn('private reasoning', answer)

    async def test_rewrite_works_without_legacy_minimax_key(self):
        answer = json.dumps({'optimized_prompt':'a wooden chair in natural light', 'matched_titles':['Chair']})
        with patch.object(matching, 'MINIMAX_API_KEY', ''), patch.object(matching, '_text_config', return_value=('test-only','https://test.invalid/v1/chat/completions','deepseek-flash')), patch.object(matching, '_chat_content', new=AsyncMock(return_value=answer)):
            result = await matching.match_prompt('chair', [{'title':'Chair','prompt':'wooden chair'}], [])
        self.assertEqual(result['optimized_prompt'], 'a wooden chair in natural light')
        self.assertEqual(result['matched_templates'][0]['title'], 'Chair')

    async def test_upstream_failure_uses_existing_fallback(self):
        with patch.object(matching, '_text_config', return_value=('test-only','https://test.invalid/v1/chat/completions','deepseek-flash')), patch.object(matching, '_chat_content', new=AsyncMock(side_effect=RuntimeError('upstream failed'))):
            result = await matching.match_prompt('chair', [], [], template_ref={'title':'Chair','prompt':'wooden chair'})
        self.assertIn('AI 服务暂时不可用', result['optimized_prompt'])

    def test_endpoint_normalization(self):
        for endpoint in ('https://test.invalid', 'https://test.invalid/v1/', 'https://test.invalid/v1/chat/completions'):
            with patch.dict(matching.os.environ, {'API_KEY':'test-only', 'Endpoint':endpoint}):
                self.assertEqual(matching._text_config()[1], 'https://test.invalid/v1/chat/completions')


if __name__ == '__main__':
    unittest.main()
