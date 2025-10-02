#!/usr/bin/env python3

"""Clean up untagged images from ECR repositories."""

import boto3


def clean_untagged_images(
    repository_prefix: str = "codeclash/", *, dry_run: bool = False, region: str = "us-east-1"
) -> None:
    ecr_client = boto3.client("ecr", region_name=region)

    response = ecr_client.describe_repositories()
    repositories = response["repositories"]

    codeclash_repos = [repo for repo in repositories if repo["repositoryName"].startswith(repository_prefix)]

    for repo in codeclash_repos:
        repo_name = repo["repositoryName"]

        images_response = ecr_client.list_images(repositoryName=repo_name)

        untagged_images = [img for img in images_response["imageIds"] if "imageTag" not in img]

        print(f"Repository: {repo_name}")
        print(f"Found {len(untagged_images)} untagged images")

        for img in untagged_images:
            digest = img["imageDigest"]
            print(f"  Image digest: {digest}")

            if not dry_run:
                ecr_client.batch_delete_image(repositoryName=repo_name, imageIds=[{"imageDigest": digest}])
                print("    Deleted")
            else:
                print("    Would delete (dry run)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="codeclash")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")

    args = parser.parse_args()

    clean_untagged_images(args.prefix, dry_run=args.dry_run, region=args.region)
