"""
AWS Lambda function for cleaning up old S3 backups based on retention policies.

This function processes backup folders in an S3 bucket and deletes backups that:
1. Are older than the configured number of days, AND
2. Are not among the last X backups to keep

This ensures that even if no new backups are uploaded, the last X backups are preserved.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')


class BackupRetentionPolicy:
    """Represents a retention policy for a backup folder."""
    
    def __init__(self, folder: str, days_to_keep: int, min_backups_to_keep: int):
        """
        Initialize retention policy.
        
        Args:
            folder: S3 folder/prefix for the backups
            days_to_keep: Delete backups older than this many days
            min_backups_to_keep: Always keep at least this many latest backups
        """
        self.folder = folder
        self.days_to_keep = days_to_keep
        self.min_backups_to_keep = min_backups_to_keep
    
    def __repr__(self):
        return (f"BackupRetentionPolicy(folder={self.folder}, "
                f"days_to_keep={self.days_to_keep}, "
                f"min_backups_to_keep={self.min_backups_to_keep})")


class S3BackupCleaner:
    """Handles S3 backup cleanup operations."""
    
    def __init__(self, bucket_name: str):
        """
        Initialize S3 backup cleaner.
        
        Args:
            bucket_name: Name of the S3 bucket containing backups
        """
        self.bucket_name = bucket_name
    
    def list_backup_objects(self, prefix: str) -> List[Dict]:
        """
        List all objects in a specific backup folder.
        
        Args:
            prefix: S3 prefix (folder) to list objects from
            
        Returns:
            List of object dictionaries with 'Key' and 'LastModified' fields
        """
        objects = []
        paginator = s3_client.get_paginator('list_objects_v2')
        
        try:
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        # Skip the folder itself (objects ending with /)
                        if not obj['Key'].endswith('/'):
                            objects.append({
                                'Key': obj['Key'],
                                'LastModified': obj['LastModified']
                            })
        except ClientError as e:
            logger.error(f"Error listing objects in {prefix}: {e}")
            raise
        
        return objects
    
    def get_objects_to_delete(
        self,
        objects: List[Dict],
        policy: BackupRetentionPolicy
    ) -> List[str]:
        """
        Determine which objects should be deleted based on retention policy.
        
        Args:
            objects: List of S3 objects with 'Key' and 'LastModified' fields
            policy: Retention policy to apply
            
        Returns:
            List of object keys to delete
        """
        if not objects:
            logger.info(f"No objects found in {policy.folder}")
            return []
        
        # Sort objects by LastModified date (newest first)
        sorted_objects = sorted(
            objects,
            key=lambda x: x['LastModified'],
            reverse=True
        )
        
        # Calculate the cutoff date
        now = datetime.now(timezone.utc)
        
        to_delete = []
        
        for idx, obj in enumerate(sorted_objects):
            # Always keep the last N backups
            if idx < policy.min_backups_to_keep:
                logger.debug(
                    f"Keeping {obj['Key']} (within last {policy.min_backups_to_keep} backups)"
                )
                continue
            
            # Check if the object is older than the retention days
            age_days = (now - obj['LastModified']).days
            
            if age_days > policy.days_to_keep:
                logger.info(
                    f"Marking {obj['Key']} for deletion (age: {age_days} days, "
                    f"policy: {policy.days_to_keep} days)"
                )
                to_delete.append(obj['Key'])
            else:
                logger.debug(
                    f"Keeping {obj['Key']} (age: {age_days} days, "
                    f"within retention period)"
                )
        
        return to_delete
    
    def delete_objects(self, keys: List[str]) -> Tuple[int, int]:
        """
        Delete objects from S3.
        
        Args:
            keys: List of object keys to delete
            
        Returns:
            Tuple of (successful_deletes, failed_deletes)
        """
        if not keys:
            logger.info("No objects to delete")
            return 0, 0
        
        successful = 0
        failed = 0
        
        # Delete in batches of 1000 (S3 limit)
        batch_size = 1000
        for i in range(0, len(keys), batch_size):
            batch = keys[i:i + batch_size]
            
            delete_objects = [{'Key': key} for key in batch]
            
            try:
                response = s3_client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={'Objects': delete_objects}
                )
                
                if 'Deleted' in response:
                    successful += len(response['Deleted'])
                    for obj in response['Deleted']:
                        logger.info(f"Successfully deleted: {obj['Key']}")
                
                if 'Errors' in response:
                    failed += len(response['Errors'])
                    for error in response['Errors']:
                        logger.error(
                            f"Failed to delete {error['Key']}: "
                            f"{error['Code']} - {error['Message']}"
                        )
            
            except ClientError as e:
                logger.error(f"Error deleting batch: {e}")
                failed += len(batch)
        
        return successful, failed
    
    def process_folder(self, policy: BackupRetentionPolicy) -> Dict:
        """
        Process a single backup folder according to its retention policy.
        
        Args:
            policy: Retention policy for the folder
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing folder: {policy.folder} with policy: {policy}")
        
        # List all objects in the folder
        objects = self.list_backup_objects(policy.folder)
        logger.info(f"Found {len(objects)} objects in {policy.folder}")
        
        # Determine which objects to delete
        to_delete = self.get_objects_to_delete(objects, policy)
        logger.info(f"Identified {len(to_delete)} objects for deletion")
        
        # Delete the objects
        successful, failed = self.delete_objects(to_delete)
        
        result = {
            'folder': policy.folder,
            'total_objects': len(objects),
            'objects_to_delete': len(to_delete),
            'deleted': successful,
            'failed': failed
        }
        
        logger.info(f"Folder {policy.folder} processing complete: {result}")
        return result


def load_retention_config(config_source: str) -> List[BackupRetentionPolicy]:
    """
    Load retention policies from a configuration source.
    
    Args:
        config_source: JSON string or S3 path (s3://bucket/key) containing config
        
    Returns:
        List of BackupRetentionPolicy objects
    """
    config_data = None
    
    # Check if config_source is an S3 path
    if config_source.startswith('s3://'):
        parts = config_source[5:].split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else 'config.json'
        
        try:
            logger.info(f"Loading config from S3: s3://{bucket}/{key}")
            response = s3_client.get_object(Bucket=bucket, Key=key)
            config_data = json.loads(response['Body'].read().decode('utf-8'))
        except ClientError as e:
            logger.error(f"Error loading config from S3: {e}")
            raise
    else:
        # Assume it's a JSON string
        try:
            config_data = json.loads(config_source)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config JSON: {e}")
            raise
    
    # Parse the configuration
    policies = []
    if 'retention_policies' in config_data:
        for policy_config in config_data['retention_policies']:
            policy = BackupRetentionPolicy(
                folder=policy_config['folder'],
                days_to_keep=policy_config.get('days_to_keep', 30),
                min_backups_to_keep=policy_config.get('min_backups_to_keep', 3)
            )
            policies.append(policy)
    
    logger.info(f"Loaded {len(policies)} retention policies")
    return policies


def lambda_handler(event, context):
    """
    Lambda handler function.
    
    Expected environment variables:
        - BUCKET_NAME: S3 bucket name containing backups
        - RETENTION_CONFIG: JSON string or S3 path with retention policies
    
    Args:
        event: Lambda event object
        context: Lambda context object
        
    Returns:
        Dictionary with processing results
    """
    logger.info(f"Lambda execution started")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Get configuration from environment variables
    bucket_name = os.environ.get('BUCKET_NAME')
    retention_config = os.environ.get('RETENTION_CONFIG')
    
    if not bucket_name:
        error_msg = "BUCKET_NAME environment variable is required"
        logger.error(error_msg)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': error_msg})
        }
    
    if not retention_config:
        error_msg = "RETENTION_CONFIG environment variable is required"
        logger.error(error_msg)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': error_msg})
        }
    
    try:
        # Load retention policies
        policies = load_retention_config(retention_config)
        
        if not policies:
            logger.warning("No retention policies found in configuration")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No retention policies configured',
                    'results': []
                })
            }
        
        # Process each folder
        cleaner = S3BackupCleaner(bucket_name)
        results = []
        
        for policy in policies:
            try:
                result = cleaner.process_folder(policy)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing folder {policy.folder}: {e}")
                results.append({
                    'folder': policy.folder,
                    'error': str(e)
                })
        
        # Calculate summary
        total_deleted = sum(r.get('deleted', 0) for r in results)
        total_failed = sum(r.get('failed', 0) for r in results)
        
        logger.info(
            f"Lambda execution complete. "
            f"Deleted: {total_deleted}, Failed: {total_failed}"
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Backup cleanup completed',
                'total_deleted': total_deleted,
                'total_failed': total_failed,
                'results': results
            })
        }
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }

