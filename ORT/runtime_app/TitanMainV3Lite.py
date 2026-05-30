from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V3L', model_label='ORTCore V3 Lite', default_interval=320, extra_env={'TITAN_LITE': '1', 'TITAN_ACCURACY_FIRST': '1'}))


if __name__ == '__main__':
    main()
