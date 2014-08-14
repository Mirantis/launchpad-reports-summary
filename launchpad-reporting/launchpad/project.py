# This is a wrapper, which converts launchpad project structure into a internal project object.

FIELDS_TO_COPY = [
    "display_name",
    "name",
    "summary"
]

class Project():

    def __init__(self, lpproject):
        
        # straight copy fields from the lpbug object. this do not make any calls to LP
        for name in FIELDS_TO_COPY:
            setattr(self, name, getattr(lpproject, name))

        # this makes additional queries to LP, but it's reasonably fast
        self.active_milestones = [str(m.name) for m in lpproject.active_milestones]
