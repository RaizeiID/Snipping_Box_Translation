from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V4L', model_label='ORTCore V4 Lite', default_interval=240, extra_env={'TITAN_HYBRID': '1', 'TITAN_LITE': '1'}))


if __name__ == '__main__':
    main()
