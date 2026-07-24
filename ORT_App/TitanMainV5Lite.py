from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V5L', model_label='ORTCore V5 Lite', default_interval=240, extra_env={'TITAN_LITE': '1', 'TITAN_NATURALIZE_MAX': '1'}))


if __name__ == '__main__':
    main()
