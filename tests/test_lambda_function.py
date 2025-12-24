"""
Unit tests for Lambda backup cleaner function.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambda_function import (
    BackupRetentionPolicy,
    S3BackupCleaner,
    load_retention_config,
    lambda_handler
)


class TestBackupRetentionPolicy(unittest.TestCase):
    """Test BackupRetentionPolicy class."""
    
    def test_initialization(self):
        """Test policy initialization."""
        policy = BackupRetentionPolicy('test-folder/', 30, 5)
        self.assertEqual(policy.folder, 'test-folder/')
        self.assertEqual(policy.days_to_keep, 30)
        self.assertEqual(policy.min_backups_to_keep, 5)
    
    def test_repr(self):
        """Test string representation."""
        policy = BackupRetentionPolicy('test/', 10, 3)
        self.assertIn('test/', repr(policy))
        self.assertIn('10', repr(policy))
        self.assertIn('3', repr(policy))


class TestS3BackupCleaner(unittest.TestCase):
    """Test S3BackupCleaner class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bucket_name = 'test-bucket'
        self.cleaner = S3BackupCleaner(self.bucket_name)
    
    @patch('lambda_function.s3_client')
    def test_list_backup_objects(self, mock_s3):
        """Test listing backup objects."""
        # Mock paginator
        mock_paginator = MagicMock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {
                        'Key': 'backups/file1.zip',
                        'LastModified': datetime(2025, 1, 1, tzinfo=timezone.utc)
                    },
                    {
                        'Key': 'backups/',  # Should be skipped
                        'LastModified': datetime(2025, 1, 1, tzinfo=timezone.utc)
                    }
                ]
            }
        ]
        
        objects = self.cleaner.list_backup_objects('backups/')
        
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]['Key'], 'backups/file1.zip')
    
    def test_get_objects_to_delete_empty(self):
        """Test with no objects."""
        policy = BackupRetentionPolicy('test/', 30, 5)
        to_delete = self.cleaner.get_objects_to_delete([], policy)
        self.assertEqual(len(to_delete), 0)
    
    def test_get_objects_to_delete_keep_minimum(self):
        """Test that minimum backups are always kept."""
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=60)
        
        objects = [
            {'Key': f'backup-{i}.zip', 'LastModified': old_date}
            for i in range(3)
        ]
        
        policy = BackupRetentionPolicy('test/', 30, 3)
        to_delete = self.cleaner.get_objects_to_delete(objects, policy)
        
        # All backups are old, but minimum 3 should be kept
        self.assertEqual(len(to_delete), 0)
    
    def test_get_objects_to_delete_by_age(self):
        """Test deletion based on age."""
        now = datetime.now(timezone.utc)
        
        objects = [
            {'Key': 'backup-1.zip', 'LastModified': now - timedelta(days=5)},
            {'Key': 'backup-2.zip', 'LastModified': now - timedelta(days=10)},
            {'Key': 'backup-3.zip', 'LastModified': now - timedelta(days=20)},
            {'Key': 'backup-4.zip', 'LastModified': now - timedelta(days=35)},
            {'Key': 'backup-5.zip', 'LastModified': now - timedelta(days=40)},
        ]
        
        policy = BackupRetentionPolicy('test/', 30, 2)
        to_delete = self.cleaner.get_objects_to_delete(objects, policy)
        
        # First 2 are kept (min_backups_to_keep)
        # backup-3.zip is 20 days old (kept)
        # backup-4.zip and backup-5.zip are older than 30 days (deleted)
        self.assertEqual(len(to_delete), 2)
        self.assertIn('backup-4.zip', to_delete)
        self.assertIn('backup-5.zip', to_delete)
    
    @patch('lambda_function.s3_client')
    def test_delete_objects(self, mock_s3):
        """Test object deletion."""
        mock_s3.delete_objects.return_value = {
            'Deleted': [{'Key': 'file1.zip'}, {'Key': 'file2.zip'}]
        }
        
        successful, failed = self.cleaner.delete_objects(['file1.zip', 'file2.zip'])
        
        self.assertEqual(successful, 2)
        self.assertEqual(failed, 0)
        mock_s3.delete_objects.assert_called_once()
    
    @patch('lambda_function.s3_client')
    def test_delete_objects_with_errors(self, mock_s3):
        """Test deletion with errors."""
        mock_s3.delete_objects.return_value = {
            'Deleted': [{'Key': 'file1.zip'}],
            'Errors': [
                {
                    'Key': 'file2.zip',
                    'Code': 'AccessDenied',
                    'Message': 'Access Denied'
                }
            ]
        }
        
        successful, failed = self.cleaner.delete_objects(['file1.zip', 'file2.zip'])
        
        self.assertEqual(successful, 1)
        self.assertEqual(failed, 1)


class TestLoadRetentionConfig(unittest.TestCase):
    """Test configuration loading."""
    
    def test_load_from_json_string(self):
        """Test loading config from JSON string."""
        config_json = json.dumps({
            'retention_policies': [
                {
                    'folder': 'test/',
                    'days_to_keep': 30,
                    'min_backups_to_keep': 5
                }
            ]
        })
        
        policies = load_retention_config(config_json)
        
        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].folder, 'test/')
        self.assertEqual(policies[0].days_to_keep, 30)
        self.assertEqual(policies[0].min_backups_to_keep, 5)
    
    @patch('lambda_function.s3_client')
    def test_load_from_s3(self, mock_s3):
        """Test loading config from S3."""
        config_data = {
            'retention_policies': [
                {
                    'folder': 's3-test/',
                    'days_to_keep': 60,
                    'min_backups_to_keep': 10
                }
            ]
        }
        
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=lambda: json.dumps(config_data).encode('utf-8'))
        }
        
        policies = load_retention_config('s3://config-bucket/config.json')
        
        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0].folder, 's3-test/')
        self.assertEqual(policies[0].days_to_keep, 60)
        self.assertEqual(policies[0].min_backups_to_keep, 10)
        
        mock_s3.get_object.assert_called_once_with(
            Bucket='config-bucket',
            Key='config.json'
        )


class TestLambdaHandler(unittest.TestCase):
    """Test Lambda handler function."""
    
    @patch.dict(os.environ, {'BUCKET_NAME': '', 'RETENTION_CONFIG': ''})
    def test_handler_missing_bucket_name(self):
        """Test handler with missing BUCKET_NAME."""
        response = lambda_handler({}, None)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('BUCKET_NAME', body['error'])
    
    @patch.dict(os.environ, {'BUCKET_NAME': 'test-bucket', 'RETENTION_CONFIG': ''})
    def test_handler_missing_config(self):
        """Test handler with missing RETENTION_CONFIG."""
        response = lambda_handler({}, None)
        
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('RETENTION_CONFIG', body['error'])
    
    @patch('lambda_function.S3BackupCleaner')
    @patch('lambda_function.load_retention_config')
    @patch.dict(os.environ, {
        'BUCKET_NAME': 'test-bucket',
        'RETENTION_CONFIG': '{"retention_policies":[]}'
    })
    def test_handler_no_policies(self, mock_load_config, mock_cleaner):
        """Test handler with no policies configured."""
        mock_load_config.return_value = []
        
        response = lambda_handler({}, None)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], 'No retention policies configured')
    
    @patch('lambda_function.S3BackupCleaner')
    @patch('lambda_function.load_retention_config')
    @patch.dict(os.environ, {
        'BUCKET_NAME': 'test-bucket',
        'RETENTION_CONFIG': '{"retention_policies":[{"folder":"test/","days_to_keep":30,"min_backups_to_keep":5}]}'
    })
    def test_handler_success(self, mock_load_config, mock_cleaner_class):
        """Test successful handler execution."""
        policy = BackupRetentionPolicy('test/', 30, 5)
        mock_load_config.return_value = [policy]
        
        mock_cleaner = MagicMock()
        mock_cleaner_class.return_value = mock_cleaner
        mock_cleaner.process_folder.return_value = {
            'folder': 'test/',
            'total_objects': 10,
            'objects_to_delete': 3,
            'deleted': 3,
            'failed': 0
        }
        
        response = lambda_handler({}, None)
        
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['total_deleted'], 3)
        self.assertEqual(body['total_failed'], 0)


if __name__ == '__main__':
    unittest.main()

