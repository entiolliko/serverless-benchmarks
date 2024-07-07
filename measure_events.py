import numpy as np
import pypapi.exceptions


def start_benchmarking(disable_gc):
    if disable_gc:
        gc.disable()
    return datetime.datetime.now()

def stop_benchmarking():
    end = datetime.datetime.now()
    gc.enable()
    return end

def check_supported_events():
    from pypapi import papi_low as papi
    from pypapi import events as papi_events

    all_events = dir(papi_events)
    all_events = [event for event in all_events if (not event.startswith('_') and not event == "PAPI_END")]
    supported_events = []

    for event_name in all_events:
        papi.library_init()
        evs = papi.create_eventset()
        try:
            event_code = getattr(papi_events, event_name)
            papi.add_event(evs, event_code)
            supported_events.append(event_name)
        except Exception as e:
            continue
            print(e)

        papi.cleanup_eventset(evs)
        papi.destroy_eventset(evs)

    return supported_events

if __name__ == "__main__":
    print(check_supported_events())
