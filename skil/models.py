import skil
from skil.services import Service

import skil_client
import time
import os
import uuid


class Model:
    """
    SKIL wrapper for DL4j, Keras and TF models

    SKIL has a robust model storage, serving, and import system for supporting major deep learning libraries.
    SKIL can be used for end-to-end training, configuration, and deployment of models or alternatively you can import models into SKIL.

    # Arguments
    model: string. Model file path.
    id: integer. Unique id for model. If `None`, a unique id will be generated.
    name: string. Name for the model.
    version: integer. Version of the model. Defaults to 1.
    experiment: `Experiment` instance. If `None`, an `Experiment` object will be created internally.
    labels: string. Labels associated with the workspace, useful for searching (comma seperated).
    verbose: boolean. If `True`, prints api response.
    create: boolean. Internal. Do not use.
    """
    def __init__(self, model=None, id=None, name=None, version=None, experiment=None,
                 labels='', verbose=False, create=True):
        if create:
            if isinstance(model, str) and os.path.isfile(model):
                model_file_name = model
            else:
                if hasattr(model, 'save'):
                    model_file_name = 'temp_model.h5'
                    if os.path.isfile(model_file_name):
                        os.remove(model_file_name)
                    model.save(model_file_name)
                else:
                    raise Exception('Invalid model: ' + str(model))
            if not experiment:
                self.skil = skil.Skil()
                self.work_space = skil.workspaces.WorkSpace(self.skil)
                self.experiment = skil.experiments.Experiment(self.work_space)
            else:
                self.experiment = experiment
                self.work_space = experiment.work_space
                self.skil = self.work_space.skil
            self.skil.upload_model(os.path.join(os.getcwd(), model_file_name))

            self.model_name = model_file_name
            self.model_path = self.skil.get_model_path(model_file_name)
            self.id = id if id else uuid.uuid1()
            self.name = name if name else model_file_name
            self.version = version if version else 1

            self.evaluations = {}

            add_model_instance_response = self.skil.api.add_model_instance(
                self.skil.server_id,
                skil_client.ModelInstanceEntity(
                    uri=self.model_path,
                    model_id=id,
                    model_labels=labels,
                    model_name=name,
                    model_version=self.version,
                    created=int(round(time.time() * 1000)),
                    experiment_id=self.experiment.id
                )
            )
            if verbose:
                self.skil.printer.pprint(add_model_instance_response)
        else:
            self.experiment = experiment
            self.work_space = experiment.work_space
            self.skil = self.work_space.skil
            assert id is not None
            self.id = id
            model_entity = self.skil.api.get_model_instance(self.skil.server_id,
                                                            id)
            self.name = model_entity.model_name
            self.version = model_entity.model_version
            self.model_path = self.skil.get_model_path(model_file_name)
            self.model = None

    def delete(self):
        """Deletes the model
        """
        try:
            self.skil.api.delete_model_instance(self.skil.server_id, self.id)
        except skil_client.rest.ApiException as e:
            self.skil.printer.pprint(
                ">>> Exception when calling delete_model_instance: %s\n" % e)

    def add_evaluation(self, accuracy, id=None, name=None, version=None):
        eval_version = version if version else 1
        eval_id = id if id else self.id
        eval_name = name if name else self.id

        eval_response = self.skil.api.add_evaluation_result(
            self.skil.server_id,
            skil_client.EvaluationResultsEntity(
                evaluation="",  # TODO: what is this?
                created=int(round(time.time() * 1000)),
                eval_name=eval_name,
                model_instance_id=self.id,
                accuracy=float(accuracy),
                eval_id=eval_id,
                eval_version=eval_version
            )
        )
        self.evaluations[id] = eval_response

    def deploy(self, deployment=None, start_server=True, scale=1, input_names=None,
               output_names=None, verbose=True):
        """Deploys the model

        # Arguments:
        deployment: `Deployment` instance.
        start_server: boolean. If `True`, the service is immedietely started.
        scale: integer. Scale for deployment.
        input_names: list of strings. Input variable names of the model.
        output_names: list of strings. Output variable names of the model.
        verbose: boolean. If `True`, api response will be printed.

        # Returns:
        `Service` instance.
        """
        if not deployment:
            deployment = skil.Deployment(skil=self.skil, name=self.name)

        uris = ["{}/model/{}/default".format(deployment.name, self.name),
                "{}/model/{}/v1".format(deployment.name, self.name)]

        deploy_model_request = skil_client.ImportModelRequest(
            name=self.name,
            scale=scale,
            file_location=self.model_path,
            model_type="model",
            uri=uris,
            input_names=input_names,
            output_names=output_names)

        self.deployment = deployment.response
        self.model_deployment = self.skil.api.deploy_model(
            self.deployment.id, deploy_model_request)
        if verbose:
            self.skil.printer.pprint(self.model_deployment)

        service = Service(self.skil, self.name, self.deployment, self.model_deployment)
        if start_server:
            service.start()
        return service

    def undeploy(self):
        """Undeploy the model.
        """
        try:
            self.skil.api.delete_model(self.deployment.id, self.id)
        except skil_client.rest.ApiException as e:
            self.skil.printer.pprint(
                ">>> Exception when calling delete_model_instance: %s\n" % e)


def get_model_by_id(self, experiment, id):
    return Model(id=id, experiment=experiment, create=False)