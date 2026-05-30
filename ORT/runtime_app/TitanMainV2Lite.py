from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V2L', model_label='ORTCore V2 Lite', default_interval=240, extra_env={'TITAN_LITE': '1', 'TITAN_LITE_NAME_ONLY': '1', 'TITAN_USE_LITE_POLICY': '1'}))


if __name__ == '__main__':
    main()
