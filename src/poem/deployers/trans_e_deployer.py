from poem.constants import GPU, KG_EMBEDDING_MODEL_NAME, EMBEDDING_DIM, LEARNING_RATE, BATCH_SIZE, NUM_EPOCHS
from poem.evaluation import RankBasedEvaluator
from poem.instance_creation_factories.triples_factory import TriplesFactory
from poem.models import TransE
from poem.preprocessing.triples_preprocessing_utils.basic_triple_utils import create_entity_and_relation_mappings, \
    load_triples, map_triples_elements_to_ids
from torch import optim
from torch import nn
import click
import numpy as np
import json
from collections import OrderedDict
import os
import time
import logging

from poem.training_loops import OWATrainingLoop

log = logging.getLogger(__name__)


@click.command()
@click.option('-training', '--training_file')
@click.option('-test', '--test_file')
@click.option('-out', '--output_direc')
def main(training_file, test_file, output_direc):
    """"""

    output_directory = os.path.join(output_direc, time.strftime("%Y-%m-%d-%H-%M-%S"))
    os.mkdir(output_directory)

    # Step 1: Create instances
    log.info("Create instances")
    training_triples = load_triples(path=training_file)

    entity_to_id, relation_to_id = create_entity_and_relation_mappings(triples=training_triples)
    mapped_training_triples = map_triples_elements_to_ids(triples=training_triples,
                                                          entity_to_id=entity_to_id,
                                                          rel_to_id=relation_to_id)
    factory = TriplesFactory(entity_to_id=entity_to_id,
                             relation_to_id=relation_to_id)

    instances = factory.create_owa_instances(triples=training_triples)

    embedding_dim = 50
    learning_rate = 0.01
    margin_loss = 1
    batch_size = 32
    num_epochs = 1

    # Step 2: Configure KGE model
    kge_model = TransE(num_entities=len(entity_to_id),
                       num_relations=len(relation_to_id),
                       embedding_dim=embedding_dim,
                       scoring_fct_norm=1,
                       criterion=nn.MarginRankingLoss(margin=1., reduction='mean'),
                       preferred_device=GPU)

    parameters = filter(lambda p: p.requires_grad, kge_model.parameters())
    optimizer = optim.SGD(params=parameters, lr=learning_rate)

    # Step 3: Train
    all_entities = np.array(list(entity_to_id.values()), dtype=np.long)
    log.info("Train KGE model")

    owa_training_loop = OWATrainingLoop(kge_model=kge_model,
                                        optimizer=optimizer,
                                        all_entities=all_entities)

    fitted_kge_model, losses = owa_training_loop.train(training_instances=instances,
                                                       num_epochs=num_epochs,
                                                       batch_size=batch_size,
                                                       )

    # Step 4: Prepare test triples
    test_triples = load_triples(path=test_file)
    mapped_test_triples = map_triples_elements_to_ids(triples=test_triples,
                                                      entity_to_id=entity_to_id,
                                                      rel_to_id=relation_to_id)

    # Step 5: Configure evaluator
    log.info("Evaluate KGE model")
    evaluator = RankBasedEvaluator(kge_model=fitted_kge_model,
                                   entity_to_id=entity_to_id,
                                   relation_to_id=relation_to_id,
                                   training_triples=mapped_training_triples,
                                   filter_neg_triples=False)

    # Step 6: Evaluate
    metric_results = evaluator.evaluate(test_triples=mapped_test_triples[0:100, :])
    results = OrderedDict()
    results['mean_rank'] = metric_results.mean_rank
    results['hits_at_k'] = metric_results.hits_at_k

    # Step 7: Create summary
    config = {
        KG_EMBEDDING_MODEL_NAME: kge_model.model_name,
        EMBEDDING_DIM: embedding_dim,
        LEARNING_RATE: learning_rate,
        BATCH_SIZE: batch_size,
        NUM_EPOCHS: num_epochs
    }

    eval_file = os.path.join(output_directory, 'evaluation_summary.json')

    with open(eval_file, 'w') as file:
        json.dump(results, file, indent=2)

    losses_file = os.path.join(output_directory, 'losses.json')

    with open(losses_file, 'w') as file:
        json.dump(losses, file, indent=2)

    config_file = os.path.join(output_directory, 'config.json')

    with open(config_file, 'w') as file:
        json.dump(config, file, indent=2)


if __name__ == '__main__':
    main()
