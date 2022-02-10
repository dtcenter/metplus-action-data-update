# metplus-action-data-update

Query web server and update data volumes used for testing.

## Inputs - Required

## `docker_name`

DockerHub username used to push images.

## `docker_pass`

DockerHub password used to push images.

## `repo_name`

Directory on DTC server to search for new data for a repo.

The text "dtcenter/" will be removed from the beginning of this value
to allow the use of ${{ github.repository }} as the value.

Examples: MET or dtcenter/MET

## `data_prefix`

Prefix of tgz files to search.

Examples: unit_test or sample_data

## `branch_name`

Name of branch that triggered logic.

Examples: develop, main_v4.1, feature_123_name, develop-ref,
feature_123_name-PR

## `docker_data_dir`

Path in Docker volume to put new data.

This is the top directory where data is added. The relative path specified
in the *volume_mount_directories* file will be appended to this path to set
as the mount point of the Docker data volume so that multiple volumes can
be mounted to the same Docker container without conflict.

## `data_repo_dev`

DockerHub repository to push development data volumes

Examples: met-data-dev, metplus-data-dev

## Inputs - Optional

## `data_repo_stable`

DockerHub repository to push data volumes for official release versions.

Used for METplus because we provide users with the sample input
data used to run the use cases using Docker and don't want to clutter the
DockerHub repository that contains these data with development versions of
test data.

## `user_feature_data`

If set to a value other than 'false', look for new data and Docker data volumes
that are named after a feature branch. If left unset, use 'develop' data for
any branches that are not main_v*.

Used for METplus to isolate new input data for a new use case.
This is done to ensure that the data fits the criteria before adding it to
the official sample dataset and to avoid corrupting or losing the existing
data.

## Outputs

None.

## Example usage

### MET
```
- uses: dtcenter/metplus-action-data-update@v1
  with:
    docker_name: ${{ secrets.DOCKER_USERNAME }}
    docker_pass: ${{ secrets.DOCKER_PASSWORD }}
    repo_name: $${{ github.repository }}
    data_prefix: unit_test
    branch_name: ${{ needs.job_control.outputs.branch_name }}
    docker_data_dir: /data/input/MET_test_data/unit_test
    data_repo_dev: met-data-dev
```

### METplus
```
- uses: dtcenter/metplus-action-data-update@v1
  with:
    docker_name: ${{ secrets.DOCKER_USERNAME }}
    docker_pass: ${{ secrets.DOCKER_PASSWORD }}
    repo_name: $${{ github.repository }}
    data_prefix: sample_data
    branch_name: ${{ needs.job_control.outputs.branch_name }}
    docker_data_dir: /data/input/METplus_Data
    data_repo_dev: metplus-data-dev
    data_repo_stable: metplus-data
    use_feature_data: true
```

## To recreate base Docker image used by action

```
docker build -t dtcenter/metplus-envs:metplus-action-data-update -f Dockerfile.env .
docker push dtcenter/metplus-envs:metplus-action-data-update
```

This should be regenerated periodically to obtain any security updates.
