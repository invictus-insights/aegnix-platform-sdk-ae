class EventRegistry:
    def __init__(self):
        self.handlers = {}

    def on(self, subject):
        """Decorator to register subject handlers."""
        def decorator(fn):
            self.handlers[subject] = fn
            return fn
        return decorator
