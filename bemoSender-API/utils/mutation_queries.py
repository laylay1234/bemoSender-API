
# TODO CHECK OWNER FIELD IN EVERYTHING ALSO CHECK this "__typename" "owner" also COLLECTTRANSACTIONS
UPDATE_USER_MUTATION = """
                    mutation UpdateUser($input: UpdateUserInput!) {
                        updateUser(input: $input) {
                            id
                            owner
                            bank_verification_status
                            createdAt
                            email
                            kyc_level
                            newsletter_subscription
                            occupation
                            phone_number
                            profileID
                            updatedAt
                            user_status
                            __typename
                            origin_country_iso
                            origin_calling_code
                            data
                            profile {
                                id
                                first_name
                                last_name
                                gender
                                country
                                __typename
                                address {
                                    id
                                    city
                                    postal_code
                                    state
                                    country{
                                        id __typename name  iso_code enabled_as_origin enabled_as_destination active calling_code createdAt updatedAt
                                    }
                                    address_line_1
                                    address_line_2
                                    createdAt
                                    updatedAt
                                    __typename
                                    owner
                                }
                                addressID
                                identity_document {
                                    id
                                    type
                                    number
                                    expiration_date
                                    createdAt
                                    updatedAt
                                    __typename
                                    owner
                                }
                                identity_documentID
                                birth_date {
                                    id
                                    date_of_birth
                                    birth_country
                                    birth_city
                                    createdAt
                                    updatedAt
                                    __typename
                                    owner
                                }
                                birth_dateID
                                createdAt
                                updatedAt
                                owner
                            }
                            global_transactions{
                                items{
                                    createdAt
                                    id
                                    userID
                                    updatedAt
                                    collect_date
                                    created_at
                                    funding_date
                                    receiverID
                                    parametersID
                                    owner
                                    status
                                    parameters{
                                        id
                                        createdAt
                                        updatedAt
                                        amount_origin
                                        amount_destination
                                        total
                                        applicable_rate
                                        transfer_reason
                                        origin_countryID
                                        destination_countryID
                                        currency_originID
                                        currency_destinationID
                                        collect_method_fee
                                        collect_method
                                        funding_method
                                        __typename
                                        owner
                                    }
                                    collect_transactions{
                                        items{
                                            id
                                            globalTransactionID
                                            img_urls
                                            collect_code
                                            partner_name
                                            status
                                            createdAt
                                            updatedAt
                                            __typename
                                        }
                                    }
                                    receiver{
                                        addressID 
                                        createdAt
                                        first_name 
                                        owner 
                                        account_number 
                                        bank_swift_code 
                                        gender 
                                        id 
                                        last_name 
                                        owner 
                                        phone_number 
                                        removed 
                                        updatedAt 
                                        userID
                                        __typename
                                    }
                                }
                            }
                            address_books {
                                items {
                                    account_number
                                    addressID
                                    bank_swift_code
                                    createdAt
                                    first_name
                                    gender
                                    id
                                    language
                                    owner
                                    last_name
                                    phone_number
                                    removed
                                    updatedAt
                                    userID
                                    __typename
                                    address {
                                        address_line_1
                                        address_line_2
                                        city
                                        country{
                                            id __typename name  iso_code enabled_as_origin enabled_as_destination active calling_code createdAt updatedAt
                                        }
                                        createdAt
                                        id
                                        owner
                                        postal_code
                                        state
                                        updatedAt
                                        __typename
                                    }
                                    transactions{
                                        items{
                                            createdAt
                                            id
                                            userID
                                            updatedAt
                                            collect_date
                                            created_at
                                            funding_date
                                            receiverID
                                            parametersID
                                            owner
                                            status
                                            __typename
                                            parameters{
                                                id
                                                createdAt
                                                updatedAt
                                                amount_origin
                                                amount_destination
                                                total
                                                applicable_rate
                                                transfer_reason
                                                origin_countryID
                                                destination_countryID
                                                currency_originID
                                                currency_destinationID
                                                collect_method_fee
                                                collect_method
                                                funding_method
                                                __typename
                                                owner
                                            }
                                            collect_transactions{
                                                items{
                                                    id
                                                    globalTransactionID
                                                    img_urls
                                                    collect_code
                                                    partner_name
                                                    status
                                                    createdAt
                                                    updatedAt
                                                    __typename
                                                }
                                            }
                                            receiver{
                                                addressID 
                                                createdAt
                                                first_name 
                                                owner 
                                                account_number 
                                                bank_swift_code 
                                                gender 
                                                id 
                                                last_name 
                                                owner 
                                                phone_number 
                                                removed 
                                                updatedAt 
                                                userID
                                                __typename
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                """


UPDATE_GLOBAL_TX_MUTATION = """
                                mutation UpdateGlobalTransaction($input: UpdateGlobalTransactionInput!) {
                                    updateGlobalTransaction(input: $input) {
                                        createdAt
                                        id
                                        userID
                                        updatedAt
                                        collect_date
                                        created_at
                                        funding_date
                                        receiverID
                                        parametersID
                                        owner
                                        status
                                        parameters{
                                            id
                                            createdAt
                                            updatedAt
                                            amount_origin
                                            amount_destination
                                            owner
                                            total
                                            applicable_rate
                                            transfer_reason
                                            origin_countryID
                                            destination_countryID
                                            currency_originID
                                            currency_destinationID
                                            collect_method_fee
                                            collect_method
                                            funding_method
                                            __typename
                                        }
                                        collect_transactions{
                                            items{
                                                id
                                                globalTransactionID
                                                img_urls
                                                collect_code
                                                partner_name
                                                status
                                                createdAt
                                                updatedAt
                                                __typename
                                            }
                                        }
                                        user{
                                            id
                                            user_status 
                                            bank_verification_status 
                                            createdAt 
                                            email kyc_level 
                                            newsletter_subscription 
                                            occupation 
                                            phone_number 
                                            profileID 
                                            updatedAt
                                               
                                            origin_country_iso 
                                            origin_calling_code 
                                            
                                            data
                                            owner
                                            __typename
                                        }
                                        receiver{
                                            addressID 
                                            createdAt
                                            first_name 
                                            owner 
                                            account_number 
                                            bank_swift_code 
                                            gender 
                                            id 
                                            last_name  
                                            phone_number 
                                            removed 
                                            updatedAt 
                                            userID
                                            __typename
                                        }

                                    }
                                }

                            """

CREATE_COUNTRY_MUTATION = """
                                mutation CreateCountry($input: CreateCountryInput!)
                                    {
                                        createCountry(input: $input){
                                            id __typename name  iso_code enabled_as_origin enabled_as_destination active calling_code createdAt updatedAt   
                                        }
                                    }
                        """
UPDATE_COUNTRY_MUTATION = """
                            mutation UpdateCountry($input: UpdateCountryInput!)
                                {
                                    updateCountry(input: $input){
                                        id __typename name  iso_code enabled_as_origin enabled_as_destination active calling_code createdAt updatedAt
                                    }
                                }
                        """

CREATE_CURRENCY_MUTATION = """
                            mutation CreateCurrency($input: CreateCurrencyInput!)
                                {
                                    createCurrency(input: $input){
                                        id __typename name  iso_code sign short_sign  createdAt updatedAt   
                                    }
                                }
                        """

UPDATE_CURRENCY_MUTATION = """
                            mutation UpdateCurrency($input: UpdateCurrencyInput!)
                                {
                                    updateCurrency(input: $input){
                                        id __typename name  iso_code sign short_sign  createdAt updatedAt   
                                    }
                                }
                            """

CREATE_COLLECT_TX_MUTATION = """
                            mutation CreateCollectTransaction($input: CreateCollectTransactionInput!)
                                {
                                    createCollectTransaction(input: $input){
                                        id __typename globalTransactionID    img_urls collect_code partner_name status createdAt updatedAt
                                    }
                                }
                            """

UPDATE_COLLECT_TX_MUTATION = """
                            mutation UpdateCollectTransaction($input: UpdateCollectTransactionInput!)
                                {
                                    updateCollectTransaction(input: $input){
                                        id __typename globalTransactionID    img_urls collect_code partner_name status createdAt updatedAt
                                    }
                                }
                            """

CREATE_APPSETTINGS_MUTATION = """
                                mutation CreateAppSettings($input: CreateAppSettingsInput!)
                                    {
                                        createAppSettings(input: $input){
                                            id __typename   content  createdAt updatedAt
                                        }
                                    }
                            """

UPDATE_APPSETTINGS_MUTATION = """
                                mutation UpdateAppSettings($input: UpdateAppSettingsInput!)
                                    {
                                        updateAppSettings(input: $input){
                                            id __typename   content  createdAt updatedAt
                                        }
                                    }
                            """

GET_GLOBAL_TRANSACTION_QUERY = """
                query MyQuery($input: ID!) {
                    getGlobalTransaction(id: $input) {
                        parametersID 
                    }
                }
"""

GET_PARAMETERS_QUERY = """
                query GetParameters($input: ID!) {
                    getParameters(id: $input) {
                        
                    }
                }
"""
UPDATE_GLOBAL_TX_PARAMETERS_MUTATION = """
                                mutation UpdateParameters($input: UpdateParametersInput!)
                                    {
                                        updateParameters(input: $input){
                                            __typename
                                            amount_destination
                                            amount_origin
                                            applicable_rate
                                            collect_method
                                            collect_method_fee
                                            createdAt
                                            currency_destination {
                                                createdAt
                                                id
                                                iso_code
                                                name
                                                short_sign
                                                sign
                                                updatedAt
                                                __typename
                                            }
                                            currency_destinationID
                                            currency_origin {
                                                createdAt
                                                id
                                                iso_code
                                                name
                                                short_sign
                                                sign
                                                updatedAt
                                                __typename
                                            }
                                            currency_originID
                                            destination_country {
                                                active
                                                calling_code
                                                createdAt
                                                enabled_as_destination
                                                enabled_as_origin
                                                id
                                                iso_code
                                                name
                                                updatedAt
                                                __typename
                                            }
                                            destination_countryID
                                            funding_method
                                            id
                                            origin_country {
                                                active
                                                calling_code
                                                createdAt
                                                enabled_as_destination
                                                enabled_as_origin
                                                id
                                                iso_code
                                                name
                                                updatedAt
                                                __typename
                                            }
                                            origin_countryID
                                            owner
                                            total
                                            transfer_reason
                                            updatedAt
                                        }
                                    }
                            """


UPDATE_PROFILE_MUTATION = """
        mutation UpdateProfile($input: UpdateProfileInput!){
            updateProfile(input: $input){
                address {
                    address_line_1
                    address_line_2
                    city
                    country {
                        active
                        calling_code
                        createdAt
                        enabled_as_destination
                        enabled_as_origin
                        id
                        iso_code
                        name
                        updatedAt
                        __typename
                    }
                    countryID
                    createdAt
                    id
                    owner
                    postal_code
                    state
                    updatedAt
                    __typename
                }
                addressID
                birth_date {
                    birth_city
                    birth_country
                    createdAt
                    date_of_birth
                    id
                    owner
                    updatedAt
                    __typename
                }
                birth_dateID
                country
                createdAt
                first_name
                gender
                id
                identity_document {
                    createdAt
                    expiration_date
                    id
                    number
                    owner
                    type
                    updatedAt
                    __typename
                }
                identity_documentID
                last_name
                owner
                updatedAt
                __typename
            }
        }

"""


UPDATE_ADDRESS_MUTATION = """
        mutation UpdateAddress($input: UpdateAddressInput!){
            updateAddress(input: $input){
                address_line_1
                address_line_2
                city
                country {
                    active
                    createdAt
                    calling_code
                    enabled_as_destination
                    enabled_as_origin
                    id
                    iso_code
                    name
                    updatedAt
                    __typename
                }
                countryID
                createdAt
                id
                owner
                postal_code
                state
                updatedAt
                __typename
            }
        }

"""

