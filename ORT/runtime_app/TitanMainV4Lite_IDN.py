from ort_unified_wrapper import run_unified


def main():
    raise SystemExit(run_unified(model_preset='V4L_IDN', model_label='ORTCore V4 Lite IDN', default_interval=240, extra_env={'TITAN_HYBRID': '1', 'TITAN_LITE': '1', 'TITAN_IDN_MODE': '1', 'TITAN_NATURALIZE_MAX': '1'}))


if __name__ == '__main__':
    main()
