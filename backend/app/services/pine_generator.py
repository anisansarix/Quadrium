import os

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates', 'pine')

def generate_pine_script(experiment_id: str, params: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template('strategy.jinja2')

    # Render template with parameters
    rendered_script = template.render(
        experiment_id=experiment_id,
        fast_ma=params.get('fast_ma', 10),
        slow_ma=params.get('slow_ma', 20)
    )
    return rendered_script
