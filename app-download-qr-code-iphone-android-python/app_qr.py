"""One QR code for an app download: iPhone to the App Store, Android to Google Play,
everyone else to a web page. Built with the Linkbreakers Python SDK.

    python app_qr.py \\
        --name "My app download" \\
        --app-store https://apps.apple.com/us/app/<your-app>/id<id> \\
        --google-play "https://play.google.com/store/apps/details?id=<your.package>" \\
        --fallback https://example.com/app
"""

import argparse
import os
import sys
from pathlib import Path

import urllib3
from dotenv import load_dotenv
from linkbreakers import (
    ApiClient,
    ClientRedirectPayload,
    Configuration,
    CreateLinkRequest,
    DevicePlatformConditionOption,
    DevicePlatformConditionPayload,
    DevicePlatformConditionValue,
    EventAction,
    LinksApi,
    ResolveQrcodeImagesRequest,
    WorkflowStepPayload,
    WorkflowStepsApi,
    WorkflowStepsServiceConnectStepBody,
    WorkflowStepsServiceCreateBody,
)
from linkbreakers.exceptions import ApiException

# Placeholders: the Wikipedia app's real store pages. Replace them with your app's.
DEFAULT_APP_STORE = "https://apps.apple.com/us/app/wikipedia/id324715238"
DEFAULT_GOOGLE_PLAY = "https://play.google.com/store/apps/details?id=org.wikipedia"
DEFAULT_FALLBACK = "https://www.wikipedia.org/"


def client() -> ApiClient:
    load_dotenv()
    token = os.environ.get("LINKBREAKERS_TOKEN")
    if not token:
        sys.exit("LINKBREAKERS_TOKEN is not set. Copy .env.example to .env and add your workspace token.")
    return ApiClient(Configuration(access_token=token, host="https://api.linkbreakers.com"))


def redirect_step(steps_api: WorkflowStepsApi, link_id: str, url: str) -> str:
    step = steps_api.workflow_steps_service_create(
        link_id,
        WorkflowStepsServiceCreateBody(
            event_action=EventAction.EVENT_ACTION_CLIENT_REDIRECT,
            payload=WorkflowStepPayload(client_redirect=ClientRedirectPayload(destination=url)),
        ),
    ).workflow_step
    return step.id


def connect(steps_api: WorkflowStepsApi, link_id: str, step_id: str, branch_id: str, next_step_id: str) -> None:
    steps_api.workflow_steps_service_connect_step(
        link_id, step_id, branch_id, WorkflowStepsServiceConnectStepBody(next_step_id=next_step_id)
    )


def create(name: str, app_store: str, google_play: str, fallback: str, qr_path: Path) -> None:
    with client() as api_client:
        links_api = LinksApi(api_client)
        steps_api = WorkflowStepsApi(api_client)

        # 1. A dynamic link whose default journey is: visit -> redirect to the fallback page.
        created = links_api.links_service_create(
            CreateLinkRequest(name=name, destination=fallback, tags=["app-download"], wait_for_qrcode=True)
        )
        link = created.link
        fallback_step = next(
            s for s in created.workflow_steps if s.event_action == EventAction.EVENT_ACTION_CLIENT_REDIRECT
        )

        # 2. One redirect per store, not connected yet.
        ios_step = redirect_step(steps_api, link.id, app_store)
        android_step = redirect_step(steps_api, link.id, google_play)

        # 3. A Device Platform condition, inserted in front of the fallback redirect:
        #    whatever led to the fallback (the link visit) now leads to the condition.
        condition = steps_api.workflow_steps_service_create(
            link.id,
            WorkflowStepsServiceCreateBody(
                event_action=EventAction.EVENT_ACTION_DEVICE_PLATFORM_CONDITION,
                payload=WorkflowStepPayload(device_platform_condition=DevicePlatformConditionPayload(options=[
                    DevicePlatformConditionOption(
                        id="ios", name="iPhone and iPad", value=DevicePlatformConditionValue.DEVICE_PLATFORM_CONDITION_VALUE_IOS
                    ),
                    DevicePlatformConditionOption(
                        id="android", name="Android", value=DevicePlatformConditionValue.DEVICE_PLATFORM_CONDITION_VALUE_ANDROID
                    ),
                ])),
                insert_before=fallback_step.id,
            ),
        ).workflow_step

        # 4. Wire each branch: option ids are the branch ids, "else" is everyone else.
        connect(steps_api, link.id, condition.id, "ios", ios_step)
        connect(steps_api, link.id, condition.id, "android", android_step)
        connect(steps_api, link.id, condition.id, "else", fallback_step.id)

        steps_api.workflow_steps_service_auto_layout_workflow(link.id, {})
        issues = steps_api.workflow_steps_service_validate_workflow(link.id).issues or []
        for issue in issues:
            print(f"workflow issue: {issue.to_dict()}")

        # 5. The QR code image. Signed URLs expire, so download it now.
        images = links_api.links_service_resolve_qrcode_images(
            ResolveQrcodeImagesRequest(link_ids=[link.id])
        ).qrcode_signed_urls or {}
        if link.id in images:
            download(images[link.id], qr_path)

    print(f"Link id:     {link.id}")
    print(f"Short link:  {link.entrypoint}")
    print(f"iOS       -> {app_store}")
    print(f"Android   -> {google_play}")
    print(f"Others    -> {fallback}")
    print(f"QR code:     {qr_path if link.id in images else 'not ready yet, download it from the dashboard'}")


def download(url: str, path: Path) -> None:
    response = urllib3.request("GET", url, timeout=30)
    if response.status != 200:
        raise RuntimeError(f"QR image download failed with HTTP {response.status}: {url}")
    path.write_bytes(response.data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default="App download")
    parser.add_argument("--app-store", default=DEFAULT_APP_STORE, help="where iOS visitors go")
    parser.add_argument("--google-play", default=DEFAULT_GOOGLE_PLAY, help="where Android visitors go")
    parser.add_argument("--fallback", default=DEFAULT_FALLBACK, help="where every other visitor goes")
    parser.add_argument("--qr", type=Path, default=Path("app-download-qr.svg"), help="where to save the QR code")
    args = parser.parse_args()

    for flag, url in (("--app-store", args.app_store), ("--google-play", args.google_play), ("--fallback", args.fallback)):
        if not url.startswith(("http://", "https://")):
            sys.exit(f"{flag} must be an http(s) URL, got {url!r}")

    try:
        create(args.name, args.app_store, args.google_play, args.fallback, args.qr)
    except ApiException as e:
        sys.exit(f"Linkbreakers API error {e.status}: {e.body}")


if __name__ == "__main__":
    main()
