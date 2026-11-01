"""Bounded case-owned binary uploads; no automatic evidence certification."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.testclient import TestClient
from server.app.adapters.profiles import ProfilesAdapter
from server.app.adapters.services import Services
from server.app.http import install_error_handlers
from server.app.settings import Settings

PDF = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n'


class LivingAttachmentTests(unittest.TestCase):
    def setUp(self):
        from server.app.living.attachments import LivingAttachments
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = Services(Settings(runtime_dir=self.temp.name))
        self.cid = ProfilesAdapter(self.ctx).create_case({})['case_id']
        self.other = ProfilesAdapter(self.ctx).create_case({})['case_id']
        self.attachments = LivingAttachments(self.ctx)
        app = FastAPI(); install_error_handlers(app,self.ctx)
        root='/api/v1/cases/{case_id}/living-services/attachments'
        app.get(root)(self.attachments.list)
        app.post(root)(self.attachments.upload)
        app.get(root+'/{attachment_id}')(self.attachments.download)
        self.client=TestClient(app)
        self.path='/api/v1/cases/'+self.cid+'/living-services/attachments'

    def upload(self, content=PDF, filename='receipt.pdf', request='upload', query=''):
        return self.client.post(self.path+query,content=content,headers={
            'Content-Type':'application/octet-stream','X-Filename':quote(filename,safe=''), 'X-Request-Id':request})

    def test_binary_upload_download_and_list_do_not_change_living_version_or_case(self):
        from server.app.living.service import LivingService
        before=ProfilesAdapter(self.ctx).read_case(self.cid)
        living=LivingService(self.ctx).read(self.cid)
        self.assertEqual(self.client.get(self.path).json(),{'items':[]})
        result=self.upload(filename='维修收据.pdf',query='?purpose=receipt')
        self.assertEqual(result.status_code,200,result.text)
        item=result.json()
        self.assertEqual(item['case_id'],self.cid)
        self.assertEqual(item['filename'],'维修收据.pdf')
        self.assertEqual(item['mime_type'],'application/pdf')
        self.assertEqual(item['purpose'],'receipt')
        self.assertEqual(item['size_bytes'],len(PDF))
        self.assertEqual(len(item['sha256']),64)
        self.assertEqual(self.client.get(self.path).json()['items'],[item])
        downloaded=self.client.get(item['download_url'])
        self.assertEqual(downloaded.content,PDF)
        self.assertEqual(downloaded.headers['x-content-type-options'],'nosniff')
        self.assertEqual(downloaded.headers['cache-control'],'no-store')
        self.assertIn('attachment;',downloaded.headers['content-disposition'])
        self.assertEqual(ProfilesAdapter(self.ctx).read_case(self.cid),before)
        self.assertEqual(LivingService(self.ctx).read(self.cid),living)
        self.assertEqual(len(list((Path(self.temp.name)/'living-files').iterdir())),1)

    def test_retry_replays_and_different_content_filename_or_purpose_conflicts(self):
        first=self.upload().json()
        self.assertEqual(self.upload().json(),first)
        for arguments in ({'content':PDF+b'\n'}, {'content':b'changed invalid bytes'}, {'filename':'other.pdf'}, {'query':'?purpose=moveout'}):
            response=self.upload(**arguments)
            self.assertEqual(response.status_code,409,response.text)
            self.assertEqual(response.json()['error']['code'],'request_conflict')
        self.assertEqual(len(self.client.get(self.path).json()['items']),1)

    def test_download_cross_case_and_missing_case_cannot_read_or_save(self):
        item=self.upload().json()
        path='/api/v1/cases/'+self.other+'/living-services/attachments/'+item['attachment_id']
        self.assertEqual(self.client.get(path).status_code,404)
        missing=self.path.replace(self.cid,'missing')
        self.assertEqual(self.client.get(missing).status_code,404)
        self.assertEqual(self.client.post(missing,content=PDF,headers={'X-Filename':'x.pdf','X-Request-Id':'x'}).status_code,404)

    def test_filename_format_and_request_identity_validation(self):
        for filename in ('../receipt.pdf','folder/receipt.pdf','folder\\receipt.pdf','bad\r\nHeader.pdf','x'*181+'.pdf','..',''):
            result=self.upload(filename=filename)
            self.assertEqual(result.status_code,422,(filename,result.text))
        for content in (b'MZ executable',b'GIF89a',b'\x89PNG\r\n\x1a\ntruncated',b'\xff\xd8\xfftruncated'):
            result=self.upload(content=content)
            self.assertEqual(result.status_code,422,result.text)
        self.assertEqual(self.upload(query='?purpose=unknown').status_code,422)
        self.assertEqual(self.upload(request='bad request').status_code,422)
        self.assertEqual(self.client.get(self.path).json()['items'],[])

    def test_png_and_jpeg_are_verified_and_mime_comes_from_bytes(self):
        from PIL import Image
        for format_,mime in (('PNG','image/png'),('JPEG','image/jpeg')):
            output=BytesIO(); Image.new('RGB',(4,4),(10,20,30)).save(output,format=format_)
            result=self.upload(output.getvalue(),filename='image.'+format_.lower(),request=format_)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['mime_type'],mime)
        self.assertEqual(len(self.client.get(self.path).json()['items']),2)

    def test_truncated_jpeg_and_mime_mismatch_are_rejected(self):
        from PIL import Image
        output=BytesIO(); Image.new('RGB',(4,4)).save(output,format='JPEG')
        result=self.upload(output.getvalue()[:-2],filename='broken.jpg')
        self.assertEqual(result.status_code,422,result.text)
        mismatch=self.client.post(self.path,content=PDF,headers={
            'Content-Type':'image/png','X-Filename':'mismatch.png','X-Request-Id':'mismatch'})
        self.assertEqual(mismatch.status_code,422,mismatch.text)
        multipart=self.client.post(self.path,files={'file':('receipt.pdf',PDF,'application/pdf')},headers={
            'X-Filename':'receipt.pdf','X-Request-Id':'multipart'})
        self.assertEqual(multipart.status_code,415,multipart.text)

    def test_size_bound_rejects_oversize_without_files(self):
        from server.app.living.attachments import MAX_FILE_BYTES
        result=self.upload(content=PDF+b' '*(MAX_FILE_BYTES+1))
        self.assertEqual(result.status_code,413,result.text)
        self.assertEqual(self.client.get(self.path).json()['items'],[])
        directory=Path(self.temp.name)/'living-files'
        self.assertFalse(directory.exists() and list(directory.iterdir()))

    def test_stream_without_length_is_still_bounded(self):
        from server.app.living import attachments as module
        with patch.object(module,'MAX_FILE_BYTES',len(PDF)+1):
            result=self.client.post(self.path,content=iter([PDF,b'X'*100]),headers={
                'Content-Type':'application/octet-stream','X-Filename':'stream.pdf','X-Request-Id':'stream'})
        self.assertEqual(result.status_code,413,result.text)
        self.assertEqual(self.client.get(self.path).json()['items'],[])

    def test_repair_reference_must_belong_to_same_case(self):
        with self.ctx.repo.transaction() as db:
            self.ctx.repo.put(db,'living_services',self.cid,{'repairs':[{'repair_id':'repair-mine'}]})
            self.ctx.repo.put(db,'living_services',self.other,{'repairs':[{'repair_id':'repair-other'}]})
        self.assertEqual(self.upload(query='?repair_id=repair-other').status_code,404)
        self.assertEqual(self.upload(query='?repair_id=missing').status_code,404)
        result=self.upload(query='?repair_id=repair-mine')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['repair_id'],'repair-mine')

    def test_case_count_and_total_byte_limits_keep_retry_available(self):
        from server.app.living import attachments as module
        first=self.upload().json()
        with patch.object(module,'MAX_CASE_FILES',1):
            self.assertEqual(self.upload().json(),first)
            self.assertEqual(self.upload(request='second').status_code,409)
        with patch.object(module,'MAX_CASE_BYTES',len(PDF)):
            self.assertEqual(self.upload().json(),first)
            self.assertEqual(self.upload(request='third').status_code,409)
        self.assertEqual(len(self.client.get(self.path).json()['items']),1)

    def test_failed_database_write_cleans_uncommitted_file(self):
        original=self.ctx.repo.put
        def fail(db,kind,identifier,value):
            if kind=='living_attachment':
                raise RuntimeError('simulated database failure')
            return original(db,kind,identifier,value)
        with patch.object(self.ctx.repo,'put',side_effect=fail):
            with self.assertRaises(RuntimeError):
                self.upload()
        self.assertEqual(self.client.get(self.path).json()['items'],[])
        directory=Path(self.temp.name)/'living-files'
        self.assertFalse(directory.exists() and list(directory.iterdir()))


if __name__=='__main__':
    unittest.main()
