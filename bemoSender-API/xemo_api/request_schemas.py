get_payment_schema = {
    "type": "object",
    "required": ['request'],
    "properties": {
        "request": {
            "type": "object",
            "required": ['service'],
            "properties": {
                "service": {
                    "type": "object",
                    "required": ['name', 'version', 'data'],
                    "properties": {
                        "name": {
                            "type": "string"
                        },
                        "version": {
                            "type": "string"
                        },
                        "data": {
                            "type": "object",
                            "required": ['paymentOrders'],
                            "properties": {
                                "paymentOrders": {

                                    "type": "array",
                                    "required": ['items'],
                                    "minItems": 1,
                                    "maxItems": 10,
                                    "uniqueItems": True,
                                    "items": {
                                        "type": "object",
                                        "required": ['payment'],
                                        "properties": {
                                            "payment": {
                                                "required": ['code'],
                                                "type": "object",
                                                "properties": {
                                                    "code": {
                                                        "oneOf": [
                                                            {
                                                                "type": "string",
                                                                "pattern": r"^[0-9]{10}$"
                                                            },
                                                            {
                                                                "type": "string",
                                                                "pattern": r"^[0-9]{14}$",
                                                            }
                                                        ]
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
confirm_payment_schema = {
    "type": "object",
    "required": ['request'],
    "properties": {
        "request": {
            "type": "object",
            "required": ['service'],
            "properties": {
                "service": {
                    "type": "object",
                    "required": ['name', 'version', 'data'],
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"},
                        "data": {
                            "type": "object",
                            "required": ['paymentOrder'],
                            "properties": {
                                "paymentOrder": {
                                    "type": "object",
                                    "required": ['payment', 'recipient', 'agency'],
                                    "properties": {
                                        "payment": {
                                            "required": ['code', 'token'],
                                            "properties": {
                                                "code": {
                                                    "oneOf": [
                                                        {
                                                            "type": "string",
                                                            "pattern": r"^[0-9]{10}$"
                                                        },
                                                        {
                                                            "type": "string",
                                                            "pattern": r"^[0-9]{14}$",
                                                        }
                                                    ]
                                                },
                                                "token": {"type": "string", "pattern": r"^[0-9a-f]{48}$"}
                                            }
                                        },
                                        "recipient": {
                                            "type": "object",
                                            "required": ['firstName', 'lastName', 'address1', 'city', 'state', 'zipcode', 'country', 'phone1', 'document'],
                                            "properties": {
                                                "firstName": {"type": "string"},
                                                "middlename": {"type": "string"},
                                                "lastName": {"type": "string"},
                                                "address1": {"type": "string"},
                                                "address2": {"type": "string"},
                                                "city": {"type": "string"},
                                                "state": {"type": "string"},
                                                "zipcode": {"type": "string"},
                                                "country": {"type": "string"},
                                                "phone1": {"type": "string"},
                                                "phone2": {"type": "string"},
                                                "document": {
                                                    "type": "object",
                                                    "required": ['type', 'number', 'country', 'expirationDate'],
                                                    "properties": {
                                                        "type": {"type": "string"},
                                                        "number": {"type": "string"},
                                                        "country": {"type": "string"},
                                                        "expirationDate": {"type": "string"}
                                                    }
                                                }
                                            }
                                        },
                                        "agency": {
                                            "type": "object",
                                            "required": ['city', 'country', 'agencyId', 'agentName'],
                                            "peroperties": {
                                                "city": {"type": "string"},
                                                "country": {"type": "string"},
                                                "agencyId": {"type": "string"},
                                                "agentName": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
rollback_payment_schema = {
    "type": "object",
    "required": ['request'],
    "properties": {
        "request": {
            "type": "object",
            "required": ['service'],
            "properties": {
                "service": {
                    "type": "object",
                    "required": ['name', 'version', 'data'],
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"},
                        "data": {
                            "type": "object",
                            "required": ['paymentOrder'],
                            "properties": {
                                "paymentOrder": {
                                    "type": "object",
                                    "required": ['payment', 'recipient', 'agency', 'rollbackReason'],
                                    "properties": {
                                        "payment": {
                                            "required": ['code', 'token'],
                                            "properties": {
                                                "code": {
                                                    "oneOf": [
                                                        {
                                                            "type": "string",
                                                            "pattern": r"^[0-9]{10}$"
                                                        },
                                                        {
                                                            "type": "string",
                                                            "pattern": r"^[0-9]{14}$",
                                                        }
                                                    ]
                                                },
                                                "token": {"type": "string", "pattern": r"^[0-9a-f]{48}$"}
                                            }
                                        },
                                        "recipient": {
                                            "type": "object",
                                            "required": ['firstName', 'lastName', 'address1', 'city', 'state', 'zipcode', 'country', 'phone1', 'document'],
                                            "properties": {
                                                "firstName": {"type": "string"},
                                                "middlename": {"type": "string"},
                                                "lastName": {"type": "string"},
                                                "address1": {"type": "string"},
                                                "address2": {"type": "string"},
                                                "city": {"type": "string"},
                                                "state": {"type": "string"},
                                                "zipcode": {"type": "string"},
                                                "country": {"type": "string"},
                                                "phone1": {"type": "string"},
                                                "phone2": {"type": "string"},
                                                "document": {
                                                    "type": "object",
                                                    "required": ['type', 'number', 'country', 'expirationDate'],
                                                    "properties": {
                                                        "type": {"type": "string"},
                                                        "number": {"type": "string"},
                                                        "country": {"type": "string"},
                                                        "expirationDate": {"type": "string"}
                                                    }
                                                }
                                            }
                                        },
                                        "agency": {
                                            "type": "object",
                                            "required": ['city', 'country', 'agencyId', 'agentName'],
                                            "peroperties": {
                                                "city": {"type": "string"},
                                                "country": {"type": "string"},
                                                "agencyId": {"type": "string"},
                                                "agentName": {"type": "string"}
                                            }
                                        },
                                        "rollbackReason": {
                                            "type": "string"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

get_daily_account_statement_schema = {
    "type": "object",
    "required": ["request"],
    "properties": {
        "request": {
            "type": "object",
            "required": ["service"],
            "properties": {
                "service": {
                    "type": "object",
                    "required": ["name", "version", "data"],
                    "properties": {
                        "name": {"type": "string"},
                        "version": {"type": "string"},
                        "data": {
                            "type": "object",
                            "required": ['statements'],
                            "properties": {
                                "statements": {
                                    "type": "array",
                                    "minItems": 1,
                                    "maxItems": 2,
                                    "uniqueItems": True,
                                    "items": {
                                        "type": "object",
                                        "required": ["account", "date"],
                                        "properties": {
                                            "account": {
                                                "type": "string",
                                                "pattern": r"[0-9A-Z]",
                                                "minLength": 4,
                                                "maxLength": 6
                                            },
                                            "date": {
                                                "type": "string",
                                                "format": "date"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
