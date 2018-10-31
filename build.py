import os
from subprocess import Popen, PIPE
from pathlib import Path
from logging import getLogger
from typing import List, Optional


log = getLogger()


DOCKER_FILE = Path('docker') / 'Dockerfile'
ARTIFACTS_DIR = Path('artifacts')


class StepFailed(Exception):
    pass


def run_command(cmd: List[str]) -> None:
    with Popen(cmd, stdout=PIPE) as proc:
        for line in proc.stdout:
            print('[make] {}'.format(line.decode()))
        proc.poll()
        proc.wait(10)
        if proc.returncode is None:
            raise Exception(f'Error executing {" ".join(cmd)}, is it hanging?')
        if proc.returncode != 0:
            raise StepFailed(proc.returncode, f'Error executing {" ".join(cmd)}, error code: {proc.returncode}')


def needs_make() -> bool:
    makefile = Path('makefile')
    return makefile.exists()


def is_master() -> bool:
    cmd1 = ['git', 'show-ref', 'origin/master', '--hash']
    out1 = None  # type: Optional[str]
    cmd2 = ['git', 'rev-parse', 'HEAD']
    out2 = None  # type: Optional[str]
    with Popen(cmd1, stdout=PIPE) as proc:
        out1, err = proc.communicate()
        if err:
            raise StepFailed(err)
    with Popen(cmd2, stdout=PIPE) as proc:
        out2, err = proc.communicate()
        if err:
            raise StepFailed(err)

    if not cmd1 or not cmd2:
        raise StepFailed('Error discovering ref repository')

    return cmd1 == cmd2


def needs_build_image() -> bool:
    return DOCKER_FILE.exists()


def needs_push_image() -> bool:
    return DOCKER_FILE.exists()


def do_push_image() -> None:
    """
    TODO: Needs aws login?
    """
    docker_image = os.getenv('DOCKER_IMAGE')
    go_pipeline_couter = os.getenv('GO_PIPELINE_COUNTER')
    if not docker_image:
        raise StepFailed('Unable to get DOCKER_IMAGE')
    if not go_pipeline_couter:
        raise StepFailed('Unable to get GO_PIPELINE_COUNTER')

    if is_master():
        build_prefix = 'master'
        add_latest = True
    else:
        build_prefix = 'pr'
        add_latest = False

    cmd1 = ['docker', 'push', f'{docker_image}:{build_prefix}-{go_pipeline_couter}']
    run_command(cmd1)

    if add_latest:
        cmd2 = ['docker', 'push', f'{docker_image}:latest']
        run_command(cmd2)


def do_build_image() -> None:
    docker_image = os.getenv('DOCKER_IMAGE')
    go_pipeline_couter = os.getenv('GO_PIPELINE_COUNTER')
    if not docker_image:
        raise StepFailed('Unable to get DOCKER_IMAGE')
    if not go_pipeline_couter:
        raise StepFailed('Unable to get GO_PIPELINE_COUNTER')

    if is_master():
        build_prefix = 'master'
        add_latest = True
    else:
        build_prefix = 'pr'
        add_latest = False

    cmd = ['docker', 'build', '-t', f'{docker_image}:{build_prefix}-{go_pipeline_couter}']
    if add_latest:
        cmd = cmd + ['-t', f'{docker_image}:latest']
    cmd = cmd + ['-f', str(DOCKER_FILE), '.']
    run_command(cmd)

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    with ARTIFACTS_DIR / 'build-id.txt' as file:
        file.write_text(f'{build_prefix}-{go_pipeline_couter}')


def do_make() -> None:
    cmd = ['make', 'all']
    run_command(cmd)


steps = [
    ('make', needs_make, do_make),
    ('build-image', needs_make, do_build_image),
    ('push-image', needs_push_image, do_push_image),
]


def run_steps() -> None:
    for (step_name, needs_step, do_step) in steps:
        if needs_step():
            log.info('Running step {step_name}')
            do_step()
        else:
            log.info(f'Step {step_name} not needed')


def main() -> None:
    run_steps()
