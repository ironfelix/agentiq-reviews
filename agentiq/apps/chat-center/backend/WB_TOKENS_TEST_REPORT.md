# Wildberries API Tokens Test Report

**Generated:** 2026-02-09 12:16:04

## Summary

| Token | Success Rate | All Passed |
|-------|--------------|------------|
| Production | 3/3 | ✅ |
| Test | 0/3 | ❌ |

## Token Details

### Production Token

**JWT Payload:**
```json
{
  "acc": 1,
  "ent": 1,
  "exp": 1786396279,
  "id": "019c41ab-6da6-765e-8fb9-e6247a69fa7e",
  "iid": 44511123,
  "oid": 4112188,
  "s": 16126,
  "sid": "764bb5eb-b610-427d-b167-904935fde848",
  "t": false,
  "uid": 44511123
}
```

**Test Results:**

1. ✅ `GET /api/v1/seller/chats`
   - Status: `200`
   - Response time: 1248ms

2. ✅ `GET /api/v1/seller/events`
   - Status: `200`
   - Response time: 366ms

3. ✅ `GET /api/v1/seller/chats`
   - Status: `200`
   - Response time: 325ms

### Test Token

**JWT Payload:**
```json
{
  "acc": 2,
  "ent": 1,
  "exp": 1786396376,
  "id": "019c41ac-e7a0-7cdd-ab2b-e803ce0923d5",
  "iid": 44511123,
  "oid": 4112188,
  "s": 0,
  "sid": "764bb5eb-b610-427d-b167-904935fde848",
  "t": true,
  "uid": 44511123
}
```

**Test Results:**

1. ❌ `GET /api/v1/seller/chats`
   - Status: `401`
   - Response time: 1323ms
   - Error: `{'title': 'unauthorized', 'detail': 'token scope not allowed', 'code': '461a0b83d6bd a53a3d31f8b003bce 8d7a4aaab17a', 'requestId': '4a36923593a61f24796c33ff3a8cd79e', 'origin': 's2s-api-auth-chatx', 'status': 401, 'statusText': 'Unauthorized', 'timestamp': '2026-02-09T09:16:02Z'}`

2. ❌ `GET /api/v1/seller/events`
   - Status: `401`
   - Response time: 660ms
   - Error: `{'title': 'unauthorized', 'detail': 'token scope not allowed', 'code': '461a0b83d6bd a53a3d31f8b003bce 8d7a4aaab17a', 'requestId': 'd346edcf318f7cd2682682564e534d17', 'origin': 's2s-api-auth-chatx', 'status': 401, 'statusText': 'Unauthorized', 'timestamp': '2026-02-09T09:16:03Z'}`

3. ❌ `GET /api/v1/seller/chats`
   - Status: `401`
   - Response time: 657ms
   - Error: `{'title': 'unauthorized', 'detail': 'token scope not allowed', 'code': '461a0b83d6bd a53a3d31f8b003bce 8d7a4aaab17a', 'requestId': '8fedfcd0b850053d58a78c38ecc5192c', 'origin': 's2s-api-auth-chatx', 'status': 401, 'statusText': 'Unauthorized', 'timestamp': '2026-02-09T09:16:04Z'}`

## Recommendations

- ✅ Use **Production token** for integration

## API Endpoints Tested

1. `GET /api/v1/seller/chats` - Get list of seller chats
2. `GET /api/v1/seller/events` - Get seller events
3. `GET /api/v1/seller/chats?limit=10&offset=0` - Get chats with pagination

## Notes

- Base URL: `https://buyer-chat-api.wildberries.ru`
- Auth method: `Authorization: <token>` header (no "Bearer" prefix)
- JWT signature algorithm: ES256 (ECDSA with SHA-256)
- Token expiration: ~August 2026
- Organization ID: 4112188
- User ID: 44511123

## Full Test Results

### Production Token Details
```json
{
  "token_name": "Production",
  "timestamp": "2026-02-09T12:15:59.993156",
  "jwt_payload": {
    "acc": 1,
    "ent": 1,
    "exp": 1786396279,
    "id": "019c41ab-6da6-765e-8fb9-e6247a69fa7e",
    "iid": 44511123,
    "oid": 4112188,
    "s": 16126,
    "sid": "764bb5eb-b610-427d-b167-904935fde848",
    "t": false,
    "uid": 44511123
  },
  "tests": [
    {
      "endpoint": "/api/v1/seller/chats",
      "method": "GET",
      "status_code": 200,
      "success": true,
      "response_time_ms": 1248,
      "response_body": {
        "result": [
          {
            "chatID": "1:2afade85-5391-5123-f7e7-eb6fb3b22251",
            "replySign": "1:2afade85-5391-5123-f7e7-eb6fb3b22251::04dd98390214c9503ce163907823703d4c5df96fb0d8ac74a0d2d2470ed6d2498fbdd6063e21970a050433cae7e29e2a20128eb3550e3d519a2a254a5139d092",
            "clientID": "",
            "clientName": "Курченко",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 335542810,
              "price": 0,
              "priceCurrency": "",
              "rid": "DAa.59be8639d7c24d4dbbedab55a8501f70.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте! У меня вопрос по товару \"Кран шаровой ВР/ВР 1/2\" бабочка, с накидной гайкой, бренд Zegor, артикул 335542810, товар оформлен 17.12.2025\" Мне ждать заказ и сколько? Может перезаказать?",
              "addTimestamp": 1766378018459
            }
          },
          {
            "chatID": "1:7da54043-2358-9346-02ac-31b632a89243",
            "replySign": "1:7da54043-2358-9346-02ac-31b632a89243::3e258679d233f003155024e79301e2324dedf20641262c30d48edbc37c23a805665865ef61cf57915fca4dddb4c25f30b53036acf4e85364a429a9ddeec462bc",
            "clientID": "",
            "clientName": "Сергей",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 446297156,
              "price": 0,
              "priceCurrency": "",
              "rid": "5087881715026823846.8.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Не заказывал",
              "addTimestamp": 1762436005554
            }
          },
          {
            "chatID": "1:18e437c4-4117-fadc-a7f5-55dd2f62aca3",
            "replySign": "1:18e437c4-4117-fadc-a7f5-55dd2f62aca3::a3268d3aa60aae47795de523bea72ddaae9d1ee6668081c2c783b47bb0a6429b3e0894a90f7db76440871ca77f88e894873e55f5fdedaad112340c4e3d8873b9",
            "clientID": "",
            "clientName": "Николай",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 381086465,
              "price": 0,
              "priceCurrency": "",
              "rid": "6413391376460536218.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Добрый день, оформите заявку на возврат, мы одобрим. Нужно чтобы упаковка была целая и товар не был в использовании.",
              "addTimestamp": 1761981368393
            }
          },
          {
            "chatID": "1:746c12b6-b32c-3292-68b7-6451357a94da",
            "replySign": "1:746c12b6-b32c-3292-68b7-6451357a94da::f238f3be470735f3b3fd629358981a2fd2f7a4e3ad2494584e06fe4bc91b7e560c006ae626e006ad21c3c1d0e9301eef26b25f36e29d59f51439f0d4f73caf0a",
            "clientID": "",
            "clientName": "Дмитрий",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 446293472,
              "price": 0,
              "priceCurrency": "",
              "rid": "21781070614800349.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Дмитрий, здравствуйте. Приносим свои извинения за задержку с отправкой заказа, в самое ближайшее время отправим товар.",
              "addTimestamp": 1760482318983
            }
          },
          {
            "chatID": "1:3989030d-d446-0b77-fd26-c89da7713664",
            "replySign": "1:3989030d-d446-0b77-fd26-c89da7713664::349b2d7c237023238f8ad64050c8ca0309e338140cd0bf299be7ef04c03f0392d2f960444aca2e80156399346de18eab38c2a724b308e95bc476bad00f6568fb",
            "clientID": "",
            "clientName": "Анастасия",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 347101885,
              "price": 0,
              "priceCurrency": "",
              "rid": "DAG.ie9e3cbe2153e2cf5bcd7ff84eec2f77b.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, доставкой занимает я маркетплейс, к сожалению не можем повлиять на скорость доставки.\nПриносим свои извинения за доставленные неудобства.",
              "addTimestamp": 1759732486514
            }
          },
          {
            "chatID": "1:8354eff6-3771-83ce-7ed5-87cf3d94d0cb",
            "replySign": "1:8354eff6-3771-83ce-7ed5-87cf3d94d0cb::3f792de778a47f3d27386953f63f9437da97b363210e43067d5fe4628441f9b3ab46d5f1e1674be2a8838797982cc6b1dd8d34dd42236ce6b49428c5e27e4713",
            "clientID": "",
            "clientName": "Алексей",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 332745174,
              "price": 0,
              "priceCurrency": "",
              "rid": "7038715393024509731.3.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Доброго вечера , так как заказ задерживается уже на три дня и продолжает задерживаться ч вынужден отказаться от вашего краника, не один нормальный человек не будет ждать больше недели задержки заказанного товара, ч уже давно купил в магазине и установил краник, так что разбирайтесь с валберис , вы теряете деньги из за доставки валберис",
              "addTimestamp": 1758736217808
            }
          },
          {
            "chatID": "1:b729b9a3-3b21-8b5a-082f-93d4a6ed9fcf",
            "replySign": "1:b729b9a3-3b21-8b5a-082f-93d4a6ed9fcf::5cf51d1fe76bae81d5103e44066dcaee30d1365193a7f2091fc9406bbc4bca22ec6136764af32eb1d422f95c98ac981d8d65b3338835a93b7e319a0f683aafab",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 335244089,
              "price": 0,
              "priceCurrency": "",
              "rid": "7558225781965755335.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Где товар",
              "addTimestamp": 1757846918448
            }
          },
          {
            "chatID": "1:f3d51142-b5bd-8bdf-aacc-334a81579cf6",
            "replySign": "1:f3d51142-b5bd-8bdf-aacc-334a81579cf6::2053d740e69ea54afd51e3433ef808d1b8a97461f8a5fc0ad7015cab475bb810567ab17141bd7db69bcc49356a921c64b21bb29698ac06748ac6cdb753947e75",
            "clientID": "",
            "clientName": "Юрий",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 356872875,
              "price": 0,
              "priceCurrency": "",
              "rid": "8550220378024349308.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Факт обмана опровергаем, на складе произошел пересорт.\nКлапан является регулируемым, вы можете настроить на 1,5 бара и использовать его.\nЕсли такой вариант вас не устраивает, товар можете вернуть.\n",
              "addTimestamp": 1756736530889
            }
          },
          {
            "chatID": "1:7c459268-aeb0-8e03-311b-37963ee56557",
            "replySign": "1:7c459268-aeb0-8e03-311b-37963ee56557::2fc666265734b300c38ba58b8a220c38a9ba90644d63ecc897e2c2caff94f3d1cbf6ed6daf95b43ddfd747143bbbcfd330ed3dca0942fad37cca8b58e4251a16",
            "clientID": "",
            "clientName": "Антон",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 356857944,
              "price": 0,
              "priceCurrency": "",
              "rid": "d5.r66f838c361c743a9addb00611b7f2354.0.5",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Расходомер идёт без ответной части",
              "addTimestamp": 1756709999643
            }
          },
          {
            "chatID": "1:d4504c3b-02fb-6bb6-bdfb-1ee46abaae81",
            "replySign": "1:d4504c3b-02fb-6bb6-bdfb-1ee46abaae81::b138b2ec9b49dbda69e6945225e2deffe794844e7bf44c245790b716370c3cdb85bd538a5f8d93347b6f606e0ac4cfafc86da1525d19fdb18b1901bab265ddbb",
            "clientID": "",
            "clientName": "Светлана",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544508,
              "price": 0,
              "priceCurrency": "",
              "rid": "6123402332514964021.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Гарантия действительна с даты покупки.",
              "addTimestamp": 1756709964954
            }
          },
          {
            "chatID": "1:80af78ed-c10d-cce4-f196-2a468f6392ac",
            "replySign": "1:80af78ed-c10d-cce4-f196-2a468f6392ac::d4f94fa439647152e9e6366eb786a1b1ec75a645301970df950a93585f49107da91c52c0470fcda709ca84b5effa111eb0e3ba45420944e9454ab283a77c314e",
            "clientID": "",
            "clientName": "Антон",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 356857944,
              "price": 0,
              "priceCurrency": "",
              "rid": "d5.r66f838c361c743a9addb00611b7f2354.0.6",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Добрый день. Ответная часть находится в коллекторе.",
              "addTimestamp": 1755582962093
            }
          },
          {
            "chatID": "1:0db0157a-610c-15c4-67cc-8c093c04d008",
            "replySign": "1:0db0157a-610c-15c4-67cc-8c093c04d008::73057365aae5b34bf533ac39f1b4c25863280933a71d2fc190cc5ca691d023f9a37c14bd1b7dd383f3a84e9bdd3661826eaf4423109eb324b9836fc371e1480c",
            "clientID": "",
            "clientName": "Алина",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586812,
              "price": 0,
              "priceCurrency": "",
              "rid": "d6.r8ab41f37bb314fac955d0f9d0654701a.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Доставкой товара занимается непосредственно маркетплейс, и сам регламентирует время доставки, к сожалению не имеем возможности на нее влиять.",
              "addTimestamp": 1754241961019
            }
          },
          {
            "chatID": "1:3ecf67e2-07b2-c3c0-78e3-452019df959d",
            "replySign": "1:3ecf67e2-07b2-c3c0-78e3-452019df959d::63c586f59c0f4ca975f4623b57e4f5c1ce9d5012de0f8a4c747f56927317357092be405f2720c210052518fd4bd44f9264a047a5a74219e9dd4009b68e00dab7",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 428211698,
              "price": 0,
              "priceCurrency": "",
              "rid": "5456247473043109280.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Добрый день. Мы не имеем возможности самостоятельно отменять заказы клиентов, не предполагает площадка.\nОбратитесь в поддержку для клиентов, вам помогут.",
              "addTimestamp": 1753961463782
            }
          },
          {
            "chatID": "1:371ed06f-44a4-bc93-1ac6-fd5d9ec24d32",
            "replySign": "1:371ed06f-44a4-bc93-1ac6-fd5d9ec24d32::ee8da4743b53cd5e9ac7ba3176f78d40f45e84764d4c567c3673edc87d1560a262fd8b9296b11eb80814c6bc685392b5cfc8b67946e7a28cc3e6b2640768e678",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586280,
              "price": 0,
              "priceCurrency": "",
              "rid": "7729853225886781682.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Благодарим за Ваше обращение. Если заказ оформили буквально недавно, то проследуйте по следующей Инструкции: зайти в раздел \"Доставки\" -> под карточкой нужного товара кнопка \"Оформлен\" -> \"Отменить заказ\" -> \"Да, отменить\". Желаем Вам всего доброго. С уважением, представитель бренда ZEGOR.",
              "addTimestamp": 1752775254145
            }
          },
          {
            "chatID": "1:2eef0aa2-b9a3-ac5a-7ff5-e6d32a0d7766",
            "replySign": "1:2eef0aa2-b9a3-ac5a-7ff5-e6d32a0d7766::692af5e42743c49fa015c1d3db4dd05d8d274e608438ad8d6e8417bca914de803d8945b212dedb9538ac873fcd7773ded4efb69466b243fc116698547d5c90b7",
            "clientID": "",
            "clientName": "Исакович Анна Витальевна",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 331719662,
              "price": 0,
              "priceCurrency": "",
              "rid": "6440102393704466040.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Заказывала 2 крана",
              "addTimestamp": 1752132333061
            }
          },
          {
            "chatID": "1:edc3c567-d211-f39a-4d42-6a66fe590b5a",
            "replySign": "1:edc3c567-d211-f39a-4d42-6a66fe590b5a::ff865c30734691b94a4729bd71a3c3dd8b55cc329fcde1cc517b18a43ac85b49919ef746915fd5f6d6ff13a38c501d67d11dfae0aba2dad789cb056f1a63c2fe",
            "clientID": "",
            "clientName": "Анатолий",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 381086465,
              "price": 0,
              "priceCurrency": "",
              "rid": "5472898163481752550.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Главное чтобы Манометр был целый и упаковка не нарушена",
              "addTimestamp": 1751703487863
            }
          },
          {
            "chatID": "1:15128b57-b251-b7af-ec8b-fcfa9e6b4d9a",
            "replySign": "1:15128b57-b251-b7af-ec8b-fcfa9e6b4d9a::0c00b75494541196046973280a3dfd4b3bce6b7b04304bb926e3a19261d6bdfcc169a25590d77b2baeaba794a37d0c81c08dee182f7781dc378eeeefca641cdd",
            "clientID": "",
            "clientName": "Алексей",
            "goodCard": {
              "date": "2025-06-20T13:38:02Z",
              "nmID": 401884254,
              "price": 42300,
              "priceCurrency": "RUB",
              "rid": "15666183610190941.0.0",
              "size": "0",
              "statusID": 1
            },
            "lastMessage": {
              "text": "Здравствуйте, Вы можете отменить заказ самостоятельно, к сожалению мы не имеем возможности отменять заказы клиентов. \nЕсли возникнут трудности, обратитесь к техподдержке вайлдберриз.",
              "addTimestamp": 1750541665911
            }
          },
          {
            "chatID": "1:71d960f7-9352-3748-daba-d03e9a7f6948",
            "replySign": "1:71d960f7-9352-3748-daba-d03e9a7f6948::baa96e151fd92bb4776ccb759e44bf5d103ff47926efaee0f04e25edcc366b77ae6f71b2a56269013d75906524aae95eeae345186f1656c8638cc8d5a910a74f",
            "clientID": "",
            "clientName": "Алексей",
            "goodCard": {
              "date": "2025-06-20T13:38:02Z",
              "nmID": 401884254,
              "price": 42300,
              "priceCurrency": "RUB",
              "rid": "15666183610190941.0.1",
              "size": "0",
              "statusID": 1
            },
            "lastMessage": {
              "text": "Здравствуйте, Вы можете отменить заказ самостоятельно, к сожалению мы не имеем возможности отменять заказы клиентов. Если возникнут трудности, обратитесь к техподдержке вайлдберриз.",
              "addTimestamp": 1750541652690
            }
          },
          {
            "chatID": "1:bd746c35-94e3-329a-07cd-1bf7479e7722",
            "replySign": "1:bd746c35-94e3-329a-07cd-1bf7479e7722::f20e316c9f20ba97ae6c46349b570afcd2cab75d2b9ae3a43211f853735274f4e7e998c75f3aacf42a66cfe1a102b252f3a67f6c2a5639011df7f37ba9962014",
            "clientID": "",
            "clientName": "Петр",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586280,
              "price": 0,
              "priceCurrency": "",
              "rid": "6521581139672999195.1.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, возврат одобрили.",
              "addTimestamp": 1750362998048
            }
          },
          {
            "chatID": "1:fcb9eaac-5a0d-f8cd-15e6-8f99815ec5f4",
            "replySign": "1:fcb9eaac-5a0d-f8cd-15e6-8f99815ec5f4::d04ef6e97ad1b5a56fa72e2b2e9289bca9058351bed0cde4ca0296b13b311079db78f7c267de269bd609eeb8dcfc9dd37b1e7a7547d9b5f07731652905385746",
            "clientID": "",
            "clientName": "Дмитрий",
            "goodCard": {
              "date": "2025-05-17T17:26:34Z",
              "nmID": 331936730,
              "price": 39400,
              "priceCurrency": "RUB",
              "rid": "d0.9b75f1bc18b844c2b0b790525b2c9ebb.0.0",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Здравствуйте. Какой вопрос?",
              "addTimestamp": 1749295147462
            }
          },
          {
            "chatID": "1:65708585-8d4b-7e3c-5525-2612abeca32e",
            "replySign": "1:65708585-8d4b-7e3c-5525-2612abeca32e::5779de4cca27c7ff5f7fdc2e4b03e8da69bfd6b151c61c6b63261eb5f6ab9edc4b30b3c45cde1f57758e53a9362d3589e08f30041201021005e8460dcb11c237",
            "clientID": "",
            "clientName": "Елена",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 252586296,
              "price": 0,
              "priceCurrency": "",
              "rid": "11034227608816433.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Коробку можете выкинуть через 2 недели после установки.",
              "addTimestamp": 1749295111806
            }
          },
          {
            "chatID": "1:bb314ddd-1085-9964-1b00-180a9e6c8b19",
            "replySign": "1:bb314ddd-1085-9964-1b00-180a9e6c8b19::8cdc05e1a21948be3f2da2aa54a7bdd62cbf869f4031f149b42511611c6f77e658ae2132cef654410364cccdeebc15a0e666a44ba84499dacd165df51cbff589",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 360755496,
              "price": 0,
              "priceCurrency": "",
              "rid": "d3.re3f2563a06c8443789f5c6fef1cc0270.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте! Здесь вы можете задать вопросы по возврату товара, если они у вас возникнут",
              "addTimestamp": 1748322586574
            }
          },
          {
            "chatID": "1:5db3b9e3-7ab1-ba43-0f97-aacc0ac9cc34",
            "replySign": "1:5db3b9e3-7ab1-ba43-0f97-aacc0ac9cc34::aee619816568ef5bc443323f4d139411da16d669fdb89774573691f4af8920423c67d6d344695c18b232bc3ec99bf56f748e2ee56e305ee843d84cb1f5dc6593",
            "clientID": "",
            "clientName": "Оксана",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 381086465,
              "price": 0,
              "priceCurrency": "",
              "rid": "8498959629396975561.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, возврат подтверждаем, будем разбираться на производстве.",
              "addTimestamp": 1746967864639
            }
          },
          {
            "chatID": "1:c2144705-8769-8109-16d0-7feb6512c075",
            "replySign": "1:c2144705-8769-8109-16d0-7feb6512c075::5d7b3cf658c4dda98cb369b83e399e89a5911b3ad99d32cbce2cf75f7be1573c3395bc5920ad29191963f80c98c7b64411cd6ff7a554a3b23ace15e6a746544e",
            "clientID": "",
            "clientName": "Тамара",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544513,
              "price": 0,
              "priceCurrency": "",
              "rid": "4623933431212927764.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, насос захватил песок вместе с водой, по инструкции его необходимо было поднять минимум 1,5 м от дна. \nДанный случай не является гарантийным.",
              "addTimestamp": 1746967707280
            }
          },
          {
            "chatID": "1:0d1ff1c1-f435-449a-6e62-bfe2d7607eea",
            "replySign": "1:0d1ff1c1-f435-449a-6e62-bfe2d7607eea::a5d2b46b51a36520ad458e82f955bae6a65d2cf55171791c20174fdfb776d39f639e55f5a7441f205782bb1b882d60575514ed2d06034f677ae5e51cd1b0ff79",
            "clientID": "",
            "clientName": "Владимир",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586280,
              "price": 0,
              "priceCurrency": "",
              "rid": "6561821447063152496.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Один из сифонов, т.е. один лишний!",
              "addTimestamp": 1746551200822
            }
          },
          {
            "chatID": "1:58f218a2-27b9-ea32-2007-cfbbca7d7a7e",
            "replySign": "1:58f218a2-27b9-ea32-2007-cfbbca7d7a7e::7c34e64a687475e526fa83ef27d397c0df161d937e523e6cad1644acf0df6bf1b12501824a2a24551d8f758bd1c061214dcadf1b1618f7b0b6f6a9ad232ffe6e",
            "clientID": "",
            "clientName": "Сергей",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 360755496,
              "price": 0,
              "priceCurrency": "",
              "rid": "dv.8983e7b9028049629a4a3ab592598b2c.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "хочу вернуть реле, потому что пришло сломаное",
              "addTimestamp": 1746198293439
            }
          },
          {
            "chatID": "1:49f57983-d801-c46e-83db-0d019cf5e80a",
            "replySign": "1:49f57983-d801-c46e-83db-0d019cf5e80a::0f1b9b0b81178e018502188846931c93700bfd4dda895e31954a934b91f9b842a7e69f22e1f465c41fe193edf5d333ccd24757b04d35a43015271252245ec31b",
            "clientID": "",
            "clientName": "Елена",
            "goodCard": {
              "date": "2025-04-23T06:56:02Z",
              "nmID": 233586811,
              "price": 39800,
              "priceCurrency": "RUB",
              "rid": "c8f7532bdb8a4b97b37b8b77920556bd",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Слушайте! Имейте совесть! Где товар???",
              "addTimestamp": 1745895477433
            }
          },
          {
            "chatID": "1:76158562-b657-1560-83c2-5df5caa9b93a",
            "replySign": "1:76158562-b657-1560-83c2-5df5caa9b93a::c25f8e74afa55021b870329b7f6d126fe96974e602a65d8b73cb60acdca186d685cebcbd8d965fcac7239a4f1e504258131e7d8554327291e72263ace665c2bd",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 252586295,
              "price": 0,
              "priceCurrency": "",
              "rid": "4754350563869886463.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Данная царапина на корпусе была обнаружена после того как вы забрали изделие с ПВЗ, Правилами  маркетплейса предусмотрено, что вы должны осмотреть товар перед тем как его забрать с пункта выдачи.\nМы всегда принимаем к возврату изделия, где обнаружен заводской брак или неисправность в работе товара.\nПри этом товар является полностью технически исправным, соответственно это не заводской брак. \nВернуть его производителю по причине брака невозможно.",
              "addTimestamp": 1745854826805
            }
          },
          {
            "chatID": "1:62d1f2c5-4e75-d34c-1d76-75a18da7edd8",
            "replySign": "1:62d1f2c5-4e75-d34c-1d76-75a18da7edd8::5774d69256dff2b6f4f15a5fb98b2fedb7fdd1b0d71ec4aaa94cc1b1e7a0fb461df70cef1dbd4d41dbc2e605f32655418acc7a9feba11dd815696b7b9a33c8ab",
            "clientID": "",
            "clientName": "Юлия",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233561764,
              "price": 0,
              "priceCurrency": "",
              "rid": "6652141906125590408.1.3",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "мы из Рязани",
              "addTimestamp": 1745744335773
            }
          },
          {
            "chatID": "1:6cde1f9b-3698-be87-2a67-f7212a8a89c0",
            "replySign": "1:6cde1f9b-3698-be87-2a67-f7212a8a89c0::bbcd06b3a66736d81b9dad26cc4108d0db0427f6d8498ce325e910af6c55c8b2fdd98f5ef5a1d813b10c860f2df1e2c4452ce17db10eb58b11c528c4e2cb714d",
            "clientID": "",
            "clientName": "Людмила",
            "goodCard": {
              "date": "2025-04-19T17:59:14Z",
              "nmID": 360755496,
              "price": 74200,
              "priceCurrency": "RUB",
              "rid": "dM.e4aa88dd5fed498a883eac392a2122a5.0.0",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Здравствуйте! У меня вопрос по товару \"Реле давления 1\" 1,4-2,8 бар (со встроенным манометром), бренд Zegor, артикул 360755496, товар оформлен 19.04.2025\" , скажите пожалуйста  а где мой заказ который должен был придти 25 апреля ????",
              "addTimestamp": 1745688034000
            }
          },
          {
            "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
            "replySign": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d::a537fe28ce9580ea1aa2ad68b9a3a2fa749d3ba8afab1a2ff7927a29e2f78bd194d90de585a8a0e23a5cbf822bfa7c054c327f164ea9bb57f8b4e99910292764",
            "clientID": "",
            "clientName": "Валентин",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544510,
              "price": 0,
              "priceCurrency": "",
              "rid": "7117333302831323250.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Просканировали данный код, Woman fashion bot, к сожалению мы не имеем отношения к данному боту. Рекламная продукция не наша.\n\nНи один из наших клиентов с данной просьбой и фото кода к нам не обращался. Это относится к категории одежда. Мы данной категорией товаров не занимаемся.\n\nВы можете задать вопрос техподдержке Вайлдберриз.\n",
              "addTimestamp": 1745686079578
            }
          },
          {
            "chatID": "1:4d18107c-626a-3e61-e6b4-57483ddec368",
            "replySign": "1:4d18107c-626a-3e61-e6b4-57483ddec368::1e7867c72fcb11b5e9287c6a6faa2f909248758c60f165dcbc9922083832d6935807dcf1bdf288268fad1fe0db251b61d1e6b59ab81be1ac823ece9e3e20e46e",
            "clientID": "",
            "clientName": "Алексей",
            "goodCard": {
              "date": "2025-04-19T05:12:35Z",
              "nmID": 233544512,
              "price": 229200,
              "priceCurrency": "RUB",
              "rid": "dw.fd4082a6a971449fb9e9f9bbc3aec60b.0.0",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Здравствуйте, мы не можем влиять на доставку и регламентировать ее срок, так как этим вопросом занимается непосредственно маркетплейс и рассчитывает ее автоматически. Вы можете обратиться в клиентскую поддержку маркетплейса.",
              "addTimestamp": 1745521655458
            }
          },
          {
            "chatID": "1:7dd73f8f-d19e-3d29-25d0-33641530716c",
            "replySign": "1:7dd73f8f-d19e-3d29-25d0-33641530716c::fb292787ca8d61a2b3a0a4702effb454668ad52c0b9871367e01386e13fa9cd36278093c9d6df15480477702832fd2842e3ce3bbf866af43ab8b32b325d3764e",
            "clientID": "",
            "clientName": "Сергей",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 360755496,
              "price": 0,
              "priceCurrency": "",
              "rid": "5753959077382472422.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Добрый день. Подскажите, заводская упаковка сохранена и внешний вид товара не поврежден? Отправьте пожалуйста фото. Если все в порядке, без проблем согласуем возврат.",
              "addTimestamp": 1745501896824
            }
          },
          {
            "chatID": "1:5465b6e1-dd53-837e-a612-0d279168601e",
            "replySign": "1:5465b6e1-dd53-837e-a612-0d279168601e::e599e7a9e9965a440af3aadf4bfb37dec1a9b2a45946b6cba7854cf5e4b7a473f90bc4a29c0ec00958a68f10bbcc4b5d8117bc4d84ac5429e6580c05128c6235",
            "clientID": "",
            "clientName": "Алптухан",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544512,
              "price": 0,
              "priceCurrency": "",
              "rid": "103868489606575313.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Верно, только воду чистую качает.",
              "addTimestamp": 1745427110104
            }
          },
          {
            "chatID": "1:a3a525a7-39e0-2bee-a687-d08b09c43fb9",
            "replySign": "1:a3a525a7-39e0-2bee-a687-d08b09c43fb9::07b1174e01e0d161d38bea142b587fa4bdb2e5feb9c6bc6260d27a5f2b6eef5fee9f7b533b84b660364b46d87cbe5bcf8459982d505ad5233fc63f2a7d5447d9",
            "clientID": "",
            "clientName": "Кирилл",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586279,
              "price": 0,
              "priceCurrency": "",
              "rid": "4725843691133682638.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Возврат одобрен.",
              "addTimestamp": 1745317851339
            }
          },
          {
            "chatID": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da",
            "replySign": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da::2f46781225e315cc2a8cb43107e9fff4fa510fc0a8974f756bf4b00220d7b1fe5d0a501c2875dbbab0c79c32affdec4dbdf18546c7b395df3520f94b35de02a1",
            "clientID": "",
            "clientName": "Игорь",
            "goodCard": {
              "date": "2025-04-12T19:06:45Z",
              "nmID": 331463403,
              "price": 39700,
              "priceCurrency": "RUB",
              "rid": "dL.9c4a05d5e5b04858b8a788c6ed5e59dd.0.0",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Вчера кран доставили. Спасибо за участие.",
              "addTimestamp": 1745227129394
            }
          },
          {
            "chatID": "1:2a1f5d20-9396-3470-d221-928abe528ceb",
            "replySign": "1:2a1f5d20-9396-3470-d221-928abe528ceb::e88a256d9fed015fb2f9c670787d10417a87567c1701c3254a4ec5a1929f8ee57273a5ae2033c464bd5dc01377cd789733f71dcebf7992002ca5c0c3b0f64a63",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 335244089,
              "price": 0,
              "priceCurrency": "",
              "rid": "d1.r660441ceb5c7414c9f1fc197e1a7bb2e.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, напишите в клиентскую поддержку вайлдберриз, мы к сожалению не имеем возможности отследить такие моменты. Доставкой занимается вайлдберриз.",
              "addTimestamp": 1745174263997
            }
          },
          {
            "chatID": "1:4dcea925-5020-1adf-f56e-9b89d29bb4e2",
            "replySign": "1:4dcea925-5020-1adf-f56e-9b89d29bb4e2::da1c4e5e88fbef7a61e93ae6a8791d0a137acf4533902b444563981ba6251b47bf76548bad0b84a7df9d3b4326056e2b723ec6decc17a26321692325adf5ada7",
            "clientID": "",
            "clientName": "Екатерина",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544512,
              "price": 0,
              "priceCurrency": "",
              "rid": "5408924234529097905.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Видимо песок или камень попал внутрь.\nВозврат одобряем.",
              "addTimestamp": 1744126064239
            }
          },
          {
            "chatID": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f",
            "replySign": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f::c4cc61a8d99c85fca0da346776b623eb6f6a01dec8a8358aa08e1f8bcb170fccdbbd3faac2d9c8fdf43060f4aeb1506c7f4a31159e2733643674473b94ad5e4f",
            "clientID": "",
            "clientName": "Олег",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544511,
              "price": 207500,
              "priceCurrency": "RUB",
              "rid": "e0aa90b5957442d2ba373900503226b4",
              "size": "0",
              "statusID": 0
            }
          }
        ],
        "errors": null
      },
      "content_type": "application/json; charset=utf-8"
    },
    {
      "endpoint": "/api/v1/seller/events",
      "method": "GET",
      "status_code": 200,
      "success": true,
      "response_time_ms": 366,
      "response_body": {
        "result": {
          "next": 1745744335773,
          "newestEventTime": "2025-04-27T08:58:55Z",
          "oldestEventTime": "2025-03-19T17:19:23Z",
          "totalEvents": 50,
          "events": [
            {
              "chatID": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f",
              "eventID": "f07b2758-c5bf-47cb-9960-5b8f1a66f9e6",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "text": "Здравствуйте! Хочу вернуть товар по заявке d7ff279e-159a-487a-9341-904559f7d1d0. Как это сделать?"
              },
              "addTimestamp": 1742404763767,
              "addTime": "2025-03-19T17:19:23Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Олег"
            },
            {
              "chatID": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f",
              "eventID": "d689e1a3-4ca6-4036-887a-f893cf7e513e",
              "eventType": "message",
              "message": {
                "text": "Как так получилоь ?"
              },
              "addTimestamp": 1742404798295,
              "addTime": "2025-03-19T17:19:58Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Олег"
            },
            {
              "chatID": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f",
              "eventID": "d60a1a32-8997-4d7e-86ab-72dce77a8eba",
              "eventType": "message",
              "message": {
                "text": "Артикул на штрихкоде один"
              },
              "addTimestamp": 1742404830426,
              "addTime": "2025-03-19T17:20:30Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Олег"
            },
            {
              "chatID": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f",
              "eventID": "9505e8e2-3be9-4365-b2e3-ef816c55f3f6",
              "eventType": "message",
              "message": {
                "text": "Артикул на упаковке другой ?"
              },
              "addTimestamp": 1742404858340,
              "addTime": "2025-03-19T17:20:58Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Олег"
            },
            {
              "chatID": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f",
              "eventID": "4572a1ff-635c-460f-b36c-7bdd357bb377",
              "eventType": "message",
              "message": {
                "text": "Заказан с верхним забором привезли с нижним "
              },
              "addTimestamp": 1742404897613,
              "addTime": "2025-03-19T17:21:37Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Олег"
            },
            {
              "chatID": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f",
              "eventID": "cd1b282f-635a-45b3-88a6-7f14c50bba16",
              "eventType": "message",
              "message": {
                "attachments": {
                  "images": [
                    {
                      "date": "2025-03-19T17:26:35.771506261Z",
                      "url": "https://static-basket-09.wbbasket.ru/vol174/chat/part2673/65472673/jpg/766e7f60-bfac-4e83-9553-7c917ca2ce1f.jpg"
                    }
                  ]
                }
              },
              "addTimestamp": 1742405196096,
              "addTime": "2025-03-19T17:26:36Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Олег"
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "32554620-f222-49fe-85a0-e98741695738",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "attachments": {
                  "goodCard": {
                    "date": "0001-01-01T00:00:00Z",
                    "nmID": 233544510,
                    "price": 0,
                    "priceCurrency": "",
                    "rid": "7117333302831323250.0.0",
                    "size": "",
                    "statusID": 0
                  }
                },
                "text": "Добрый вечер! Купил насос: хороший. Подскажите что с этим делать?"
              },
              "addTimestamp": 1743183306049,
              "addTime": "2025-03-28T17:35:06Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "83e29df3-5040-4d8e-b218-c72e469603f7",
              "eventType": "message",
              "message": {
                "attachments": {
                  "images": [
                    {
                      "date": "2025-03-28T20:35:26.858+03:00",
                      "url": "https://static-basket-09.wbbasket.ru/vol174/chat/part2957/17802957/jpeg/026b03c0-4d20-4111-81e3-058e46ccf60b.jpeg"
                    }
                  ]
                }
              },
              "addTimestamp": 1743183327102,
              "addTime": "2025-03-28T17:35:27Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "06ef062e-5404-4af7-a86d-007a9d2f70e1",
              "eventType": "message",
              "message": {
                "attachments": {
                  "images": [
                    {
                      "date": "2025-03-28T20:35:56.185+03:00",
                      "url": "https://static-basket-09.wbbasket.ru/vol174/chat/part2957/17802957/jpeg/971a8237-d620-4e39-abad-d513050fb25e.jpeg"
                    }
                  ]
                }
              },
              "addTimestamp": 1743183356490,
              "addTime": "2025-03-28T17:35:56Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "477e9d35-f243-4fff-9672-873d9ca8e7d8",
              "eventType": "message",
              "message": {
                "text": "первое фото  случайно"
              },
              "addTimestamp": 1743183371808,
              "addTime": "2025-03-28T17:36:11Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:4dcea925-5020-1adf-f56e-9b89d29bb4e2",
              "eventID": "275477ab-96ee-47e9-be90-17fec5b6e09a",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "text": "Здравствуйте! Здесь вы можете задать вопросы по возврату товара, если они у вас возникнут"
              },
              "addTimestamp": 1744105721984,
              "addTime": "2025-04-08T09:48:41Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:4dcea925-5020-1adf-f56e-9b89d29bb4e2",
              "eventID": "954c2a31-b5d9-47e1-ae72-53da1616b719",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте.Вероятнее всего, Вы опустили насос на дно, и вместе с водой насос захватил песок. Для восстановления его производительности необходимо промыть насос.\n\nВ случае того, если данная процедура не поможет, одобрим Вам возврат."
              },
              "addTimestamp": 1744115683053,
              "addTime": "2025-04-08T12:34:43Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:4dcea925-5020-1adf-f56e-9b89d29bb4e2",
              "eventID": "34c20a2b-476d-4b90-9acf-9e7a3b6c2e7e",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте. А как его промыть? Там что-то гремит еще."
              },
              "addTimestamp": 1744115853600,
              "addTime": "2025-04-08T12:37:33Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Екатерина"
            },
            {
              "chatID": "1:4dcea925-5020-1adf-f56e-9b89d29bb4e2",
              "eventID": "50bcaffb-3479-4414-a748-e6c129c9105c",
              "eventType": "message",
              "message": {
                "text": "Видимо песок или камень попал внутрь.\nВозврат одобряем."
              },
              "addTimestamp": 1744126064239,
              "addTime": "2025-04-08T15:27:44Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:5465b6e1-dd53-837e-a612-0d279168601e",
              "eventID": "0154908c-7ae3-4883-bdba-f7aba7f9555a",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "text": "Здравствуйте! Здесь вы можете задать вопросы по возврату товара, если они у вас возникнут"
              },
              "addTimestamp": 1744126149117,
              "addTime": "2025-04-08T15:29:09Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:5465b6e1-dd53-837e-a612-0d279168601e",
              "eventID": "398bfe8a-ce85-4cad-bab7-192f2691b56e",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте. Чем Вас не устроил данный насос?"
              },
              "addTimestamp": 1744126296465,
              "addTime": "2025-04-08T15:31:36Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:5465b6e1-dd53-837e-a612-0d279168601e",
              "eventID": "d0d6bd29-3bc8-41d4-bd08-4a6590d0ef86",
              "eventType": "message",
              "message": {
                "text": "Добрый день не правильно товар заказал  мне\n Надо качат масло это насос получается толко вода правильно?"
              },
              "addTimestamp": 1744127214015,
              "addTime": "2025-04-08T15:46:54Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Алптухан"
            },
            {
              "chatID": "1:2a1f5d20-9396-3470-d221-928abe528ceb",
              "eventID": "11737aeb-2d07-4e08-a811-07ca3383da74",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "attachments": {
                  "goodCard": {
                    "date": "0001-01-01T00:00:00Z",
                    "nmID": 335244089,
                    "price": 0,
                    "priceCurrency": "",
                    "rid": "d1.r660441ceb5c7414c9f1fc197e1a7bb2e.0.0",
                    "size": "",
                    "statusID": 0
                  }
                },
                "text": "ваш товар на каком-то складе завис и не куда не движется товар ждать или нет"
              },
              "addTimestamp": 1744907378123,
              "addTime": "2025-04-17T16:29:38Z",
              "sender": "client",
              "clientID": ""
            },
            {
              "chatID": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da",
              "eventID": "8ab08868-68db-41f5-99af-efc906196e60",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "text": "Здравствуйте! У меня вопрос по товару \"Кран шаровой ВР/НР/НР 1/2\"х3/4\"х1/2\" для сантех. приборов, бренд Zegor, артикул 331463403, товар оформлен 12.04.2025\""
              },
              "addTimestamp": 1744916040467,
              "addTime": "2025-04-17T18:54:00Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Игорь"
            },
            {
              "chatID": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da",
              "eventID": "674fa84b-c0dc-4dcd-9ecd-654686d28806",
              "eventType": "message",
              "message": {
                "text": "Прошу сообщить, когда привезут кран. "
              },
              "addTimestamp": 1744916108772,
              "addTime": "2025-04-17T18:55:08Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Игорь"
            },
            {
              "chatID": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da",
              "eventID": "8cbc479e-3163-4b03-85ff-6645a7203729",
              "eventType": "message",
              "message": {
                "text": "К сожалению продавец молчит. На вопрос: \"Когда привезут кран?\" - молчит. Кран нужен вчера. Жду ответа.\n"
              },
              "addTimestamp": 1744968408398,
              "addTime": "2025-04-18T09:26:48Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Игорь"
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "2f4cc72a-c42b-4446-b9b8-6f38cf2224f9",
              "eventType": "message",
              "message": {
                "text": "Добрый вечер! Купил насос: хороший. Подскажите что с этим делать?"
              },
              "addTimestamp": 1745150568468,
              "addTime": "2025-04-20T12:02:48Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "e05c0bf9-3851-4d14-8039-bcd944f31c64",
              "eventType": "message",
              "message": {
                "attachments": {
                  "images": [
                    {
                      "date": "2025-04-20T15:02:56.475+03:00",
                      "url": "https://static-basket-09.wbbasket.ru/vol174/chat/part2957/17802957/jpeg/45fc83bb-41aa-4a5c-a01e-1656d0b94f69.jpeg"
                    }
                  ]
                }
              },
              "addTimestamp": 1745150577258,
              "addTime": "2025-04-20T12:02:57Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "fa3cb579-539d-4d20-9853-a4ce2c53b646",
              "eventType": "message",
              "message": {
                "text": "отзыв написал"
              },
              "addTimestamp": 1745150583376,
              "addTime": "2025-04-20T12:03:03Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da",
              "eventID": "b40b788d-3ca9-4b97-8439-edbf3bee8dd6",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте,  к сожалению не имеем возможности влиять на доставку. Мы отгружаем товар, а далее доставку регламентирует маркетплейс."
              },
              "addTimestamp": 1745174214063,
              "addTime": "2025-04-20T18:36:54Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:2a1f5d20-9396-3470-d221-928abe528ceb",
              "eventID": "aa5eccb9-1a80-4ee0-b11c-b5174f71e0be",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте, напишите в клиентскую поддержку вайлдберриз, мы к сожалению не имеем возможности отследить такие моменты. Доставкой занимается вайлдберриз."
              },
              "addTimestamp": 1745174263997,
              "addTime": "2025-04-20T18:37:43Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da",
              "eventID": "98fcdde7-6cb3-4749-ab34-b1b0cd2044c1",
              "eventType": "message",
              "message": {
                "text": "Вчера кран доставили. Спасибо за участие."
              },
              "addTimestamp": 1745227129394,
              "addTime": "2025-04-21T09:18:49Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Игорь"
            },
            {
              "chatID": "1:a3a525a7-39e0-2bee-a687-d08b09c43fb9",
              "eventID": "5833ebf7-15be-4df9-b00f-2a19865c883f",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "text": "Здравствуйте! Здесь вы можете задать вопросы по возврату товара, если они у вас возникнут"
              },
              "addTimestamp": 1745264760165,
              "addTime": "2025-04-21T19:46:00Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:a3a525a7-39e0-2bee-a687-d08b09c43fb9",
              "eventID": "4d1f5e50-2256-453e-882c-298de52a07e3",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте. Вы можете продавить пластиковый квадрат, для отверстия перелива."
              },
              "addTimestamp": 1745264848800,
              "addTime": "2025-04-21T19:47:28Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:a3a525a7-39e0-2bee-a687-d08b09c43fb9",
              "eventID": "9aecf2b7-afa2-44cf-b7db-8a0439431d22",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте,я не хочу продавливать.\nПоломаю потом не верну.Примите пожалуйста возврат."
              },
              "addTimestamp": 1745266151574,
              "addTime": "2025-04-21T20:09:11Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Кирилл"
            },
            {
              "chatID": "1:a3a525a7-39e0-2bee-a687-d08b09c43fb9",
              "eventID": "52a472bf-29e7-4326-b2d7-feee65d38fcb",
              "eventType": "message",
              "message": {
                "text": "Возврат одобрен."
              },
              "addTimestamp": 1745317851339,
              "addTime": "2025-04-22T10:30:51Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "08dc1414-574d-4f35-8fbb-3b2a1b02a9b4",
              "eventType": "message",
              "message": {
                "text": "ау"
              },
              "source": "android",
              "addTimestamp": 1745417151773,
              "addTime": "2025-04-23T14:05:51Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:5465b6e1-dd53-837e-a612-0d279168601e",
              "eventID": "036b6008-2c12-45ae-8600-bf15fe879757",
              "eventType": "message",
              "message": {
                "text": "Верно, только воду чистую качает."
              },
              "source": "seller-portal",
              "addTimestamp": 1745427110104,
              "addTime": "2025-04-23T16:51:50Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:7dd73f8f-d19e-3d29-25d0-33641530716c",
              "eventID": "cdfd113c-e26f-4f91-9161-47bfdafb814c",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "attachments": {
                  "goodCard": {
                    "date": "0001-01-01T00:00:00Z",
                    "nmID": 360755496,
                    "price": 0,
                    "priceCurrency": "",
                    "rid": "5753959077382472422.0.0",
                    "size": "",
                    "statusID": 0
                  }
                },
                "text": "Здравствуйте! Здесь вы можете задать вопросы по возврату товара, если они у вас возникнут"
              },
              "source": "seller-portal",
              "addTimestamp": 1745501798197,
              "addTime": "2025-04-24T13:36:38Z",
              "replySign": "1:7dd73f8f-d19e-3d29-25d0-33641530716c::209ff8406a2728021bc625026c90686b86cc609a8bf7ade150ecab9b94c706a034070c064263fd504fb9d3265dca3430650a451ac725c0e48a8e88e2f2b56e9d",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:7dd73f8f-d19e-3d29-25d0-33641530716c",
              "eventID": "3ec020c6-1062-4849-8f45-92ad108946a5",
              "eventType": "message",
              "message": {
                "text": "Добрый день. Подскажите, заводская упаковка сохранена и внешний вид товара не поврежден? Отправьте пожалуйста фото. Если все в порядке, без проблем согласуем возврат."
              },
              "source": "seller-portal",
              "addTimestamp": 1745501896824,
              "addTime": "2025-04-24T13:38:16Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:4d18107c-626a-3e61-e6b4-57483ddec368",
              "eventID": "b47f4a37-dba6-4929-864e-5ac0be169a33",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "attachments": {
                  "goodCard": {
                    "date": "2025-04-19T05:12:35Z",
                    "nmID": 233544512,
                    "price": 229200,
                    "priceCurrency": "RUB",
                    "rid": "dw.fd4082a6a971449fb9e9f9bbc3aec60b.0.0",
                    "size": "0",
                    "statusID": 3
                  }
                },
                "text": "Здравствуйте! У меня вопрос по товару \"Насос вибрационный ZVM60B-10 верхний забор, кабель 10 метров, бренд Zegor, артикул 233544512, товар оформлен 19.04.2025\""
              },
              "source": "rusite",
              "addTimestamp": 1745503658310,
              "addTime": "2025-04-24T14:07:38Z",
              "replySign": "1:4d18107c-626a-3e61-e6b4-57483ddec368::8100f1875fb5b325014bf3ff16e28dbb16a401d7c91ca9e12cb54be8ad667c63674103f77dd265474ca6a41b335f0609a2eca9570967fa9f7c32949ef4f5ce1b",
              "sender": "client",
              "clientID": "",
              "clientName": "Алексей"
            },
            {
              "chatID": "1:4d18107c-626a-3e61-e6b4-57483ddec368",
              "eventID": "7c53c983-f99f-4b75-aefb-74ca69b92210",
              "eventType": "message",
              "message": {
                "text": "где ваш насос передали на склад и всё какието движения далее будут или нет"
              },
              "source": "rusite",
              "addTimestamp": 1745503791802,
              "addTime": "2025-04-24T14:09:51Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Алексей"
            },
            {
              "chatID": "1:4d18107c-626a-3e61-e6b4-57483ddec368",
              "eventID": "3cbc992d-fdf1-42cf-8a0c-cad053172ba6",
              "eventType": "message",
              "message": {
                "text": "почему не отвечаете на вопрос"
              },
              "source": "rusite",
              "addTimestamp": 1745505837537,
              "addTime": "2025-04-24T14:43:57Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Алексей"
            },
            {
              "chatID": "1:4d18107c-626a-3e61-e6b4-57483ddec368",
              "eventID": "129666b7-c1c3-474e-9270-af9221fe956a",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте, мы не можем влиять на доставку и регламентировать ее срок, так как этим вопросом занимается непосредственно маркетплейс и рассчитывает ее автоматически. Вы можете обратиться в клиентскую поддержку маркетплейса."
              },
              "source": "seller-portal",
              "addTimestamp": 1745521655458,
              "addTime": "2025-04-24T19:07:35Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "7afe18db-733a-4497-a851-f9d5f32e941f",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте, данная рекламная продукция не имеет отношения к товару. Вероятнее всего, на сортировке произошел пересорт с другим продавцом. "
              },
              "source": "seller-portal",
              "addTimestamp": 1745521783990,
              "addTime": "2025-04-24T19:09:43Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "741dbafb-8cec-49bd-b800-3c448491da0f",
              "eventType": "message",
              "message": {
                "text": "что значит не имеет: по коду отправляет на ваш сайт. соответственно по нему должны сделать бонус вы 200"
              },
              "source": "android",
              "addTimestamp": 1745616013038,
              "addTime": "2025-04-25T21:20:13Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "6482286f-ad77-4c33-ad5c-a9c2b500f840",
              "eventType": "message",
              "message": {
                "text": "или ваша компания не выполняете своих условий?"
              },
              "source": "android",
              "addTimestamp": 1745616042014,
              "addTime": "2025-04-25T21:20:42Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Валентин"
            },
            {
              "chatID": "1:76158562-b657-1560-83c2-5df5caa9b93a",
              "eventID": "f8dc2f39-4460-4c67-bee4-343782ba8708",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "attachments": {
                  "goodCard": {
                    "date": "0001-01-01T00:00:00Z",
                    "nmID": 252586295,
                    "price": 0,
                    "priceCurrency": "",
                    "rid": "4754350563869886463.0.0",
                    "size": "",
                    "statusID": 0
                  }
                },
                "text": "Здравствуйте! Здесь вы можете задать вопросы по возврату товара, если они у вас возникнут"
              },
              "source": "seller-portal",
              "addTimestamp": 1745673655300,
              "addTime": "2025-04-26T13:20:55Z",
              "replySign": "1:76158562-b657-1560-83c2-5df5caa9b93a::fe9b0d1b053be03e27b101dbc27df7774026c42cf8c7566fe1cb0259493549517718c4ed36f5f927d8b55e5d90b316ab21e701e93d4c9787e7f162621d0c83b2",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:76158562-b657-1560-83c2-5df5caa9b93a",
              "eventID": "793a897a-f5c7-4296-883f-36a08dd359ff",
              "eventType": "message",
              "message": {
                "text": "Здравствуйте, не сможем принять возврат, так как в данном случае вины продавца нет, товар не был осмотрен на ПВЗ и отказа не последовало. \nТовар является полностью технически исправным."
              },
              "source": "seller-portal",
              "addTimestamp": 1745673881027,
              "addTime": "2025-04-26T13:24:41Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "6470b7bc-4339-43b1-ac6f-74aca987e7b0",
              "eventType": "message",
              "message": {
                "text": "Напишите, на какой сайт отправляет?"
              },
              "source": "seller-portal",
              "addTimestamp": 1745685570531,
              "addTime": "2025-04-26T16:39:30Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "c3d9928a-49f4-4c74-9517-01dde91e361c",
              "eventType": "message",
              "message": {
                "text": "Обязательно разберемся в ситуации."
              },
              "source": "seller-portal",
              "addTimestamp": 1745685627577,
              "addTime": "2025-04-26T16:40:27Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
              "eventID": "084f06f2-1f11-4a9c-8df0-ab57fc799963",
              "eventType": "message",
              "message": {
                "text": "Просканировали данный код, Woman fashion bot, к сожалению мы не имеем отношения к данному боту. Рекламная продукция не наша.\n\nНи один из наших клиентов с данной просьбой и фото кода к нам не обращался. Это относится к категории одежда. Мы данной категорией товаров не занимаемся.\n\nВы можете задать вопрос техподдержке Вайлдберриз.\n"
              },
              "source": "seller-portal",
              "addTimestamp": 1745686079578,
              "addTime": "2025-04-26T16:47:59Z",
              "sender": "seller",
              "clientID": ""
            },
            {
              "chatID": "1:6cde1f9b-3698-be87-2a67-f7212a8a89c0",
              "eventID": "98ab5a42-681b-4cbc-a776-fd81f9fdf5e9",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "attachments": {
                  "goodCard": {
                    "date": "2025-04-19T17:59:14Z",
                    "nmID": 360755496,
                    "price": 74200,
                    "priceCurrency": "RUB",
                    "rid": "dM.e4aa88dd5fed498a883eac392a2122a5.0.0",
                    "size": "0",
                    "statusID": 3
                  }
                },
                "text": "Здравствуйте! У меня вопрос по товару \"Реле давления 1\" 1,4-2,8 бар (со встроенным манометром), бренд Zegor, артикул 360755496, товар оформлен 19.04.2025\" , скажите пожалуйста  а где мой заказ который должен был придти 25 апреля ????"
              },
              "source": "rusite",
              "addTimestamp": 1745688034000,
              "addTime": "2025-04-26T17:20:34Z",
              "replySign": "1:6cde1f9b-3698-be87-2a67-f7212a8a89c0::9f0e1e706ad54314c0d8369f365bdc57d7de1092f15b030c6246ded5878068a085d3d3b088833ee2d6a790bcca7e85500abe57e517fc5105bcdddf1e3c3a7ef9",
              "sender": "client",
              "clientID": "",
              "clientName": "Людмила"
            },
            {
              "chatID": "1:62d1f2c5-4e75-d34c-1d76-75a18da7edd8",
              "eventID": "79c0549b-35ca-4898-9101-d632a7e322e9",
              "eventType": "message",
              "isNewChat": true,
              "message": {
                "attachments": {
                  "goodCard": {
                    "date": "0001-01-01T00:00:00Z",
                    "nmID": 233561764,
                    "price": 0,
                    "priceCurrency": "",
                    "rid": "6652141906125590408.1.3",
                    "size": "",
                    "statusID": 0
                  }
                },
                "text": "здравствуйте, купили у вас 9 шлангов , а оказалось не хватает длины, хотим перезаказать побольше. как лучше это сделать?"
              },
              "source": "android",
              "addTimestamp": 1745743444273,
              "addTime": "2025-04-27T08:44:04Z",
              "replySign": "1:62d1f2c5-4e75-d34c-1d76-75a18da7edd8::f38638880efe8ffc97512ccd98a447f185d4e8556aa65d7749c7c142c9982d4df7ea7c06918e2910093682085e9b71744960f09efeb4628814621fb41cf25225",
              "sender": "client",
              "clientID": "",
              "clientName": "Юлия"
            },
            {
              "chatID": "1:62d1f2c5-4e75-d34c-1d76-75a18da7edd8",
              "eventID": "98b0daa8-7b97-4296-a915-52eaa5d6b103",
              "eventType": "message",
              "message": {
                "text": "мы из Рязани"
              },
              "source": "android",
              "addTimestamp": 1745744335773,
              "addTime": "2025-04-27T08:58:55Z",
              "sender": "client",
              "clientID": "",
              "clientName": "Юлия"
            }
          ]
        },
        "errors": null
      },
      "content_type": "application/json; charset=utf-8"
    },
    {
      "endpoint": "/api/v1/seller/chats",
      "method": "GET",
      "status_code": 200,
      "success": true,
      "response_time_ms": 325,
      "response_body": {
        "result": [
          {
            "chatID": "1:2afade85-5391-5123-f7e7-eb6fb3b22251",
            "replySign": "1:2afade85-5391-5123-f7e7-eb6fb3b22251::04dd98390214c9503ce163907823703d4c5df96fb0d8ac74a0d2d2470ed6d2498fbdd6063e21970a050433cae7e29e2a20128eb3550e3d519a2a254a5139d092",
            "clientID": "",
            "clientName": "Курченко",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 335542810,
              "price": 0,
              "priceCurrency": "",
              "rid": "DAa.59be8639d7c24d4dbbedab55a8501f70.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте! У меня вопрос по товару \"Кран шаровой ВР/ВР 1/2\" бабочка, с накидной гайкой, бренд Zegor, артикул 335542810, товар оформлен 17.12.2025\" Мне ждать заказ и сколько? Может перезаказать?",
              "addTimestamp": 1766378018459
            }
          },
          {
            "chatID": "1:7da54043-2358-9346-02ac-31b632a89243",
            "replySign": "1:7da54043-2358-9346-02ac-31b632a89243::3e258679d233f003155024e79301e2324dedf20641262c30d48edbc37c23a805665865ef61cf57915fca4dddb4c25f30b53036acf4e85364a429a9ddeec462bc",
            "clientID": "",
            "clientName": "Сергей",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 446297156,
              "price": 0,
              "priceCurrency": "",
              "rid": "5087881715026823846.8.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Не заказывал",
              "addTimestamp": 1762436005554
            }
          },
          {
            "chatID": "1:18e437c4-4117-fadc-a7f5-55dd2f62aca3",
            "replySign": "1:18e437c4-4117-fadc-a7f5-55dd2f62aca3::a3268d3aa60aae47795de523bea72ddaae9d1ee6668081c2c783b47bb0a6429b3e0894a90f7db76440871ca77f88e894873e55f5fdedaad112340c4e3d8873b9",
            "clientID": "",
            "clientName": "Николай",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 381086465,
              "price": 0,
              "priceCurrency": "",
              "rid": "6413391376460536218.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Добрый день, оформите заявку на возврат, мы одобрим. Нужно чтобы упаковка была целая и товар не был в использовании.",
              "addTimestamp": 1761981368393
            }
          },
          {
            "chatID": "1:746c12b6-b32c-3292-68b7-6451357a94da",
            "replySign": "1:746c12b6-b32c-3292-68b7-6451357a94da::f238f3be470735f3b3fd629358981a2fd2f7a4e3ad2494584e06fe4bc91b7e560c006ae626e006ad21c3c1d0e9301eef26b25f36e29d59f51439f0d4f73caf0a",
            "clientID": "",
            "clientName": "Дмитрий",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 446293472,
              "price": 0,
              "priceCurrency": "",
              "rid": "21781070614800349.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Дмитрий, здравствуйте. Приносим свои извинения за задержку с отправкой заказа, в самое ближайшее время отправим товар.",
              "addTimestamp": 1760482318983
            }
          },
          {
            "chatID": "1:3989030d-d446-0b77-fd26-c89da7713664",
            "replySign": "1:3989030d-d446-0b77-fd26-c89da7713664::349b2d7c237023238f8ad64050c8ca0309e338140cd0bf299be7ef04c03f0392d2f960444aca2e80156399346de18eab38c2a724b308e95bc476bad00f6568fb",
            "clientID": "",
            "clientName": "Анастасия",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 347101885,
              "price": 0,
              "priceCurrency": "",
              "rid": "DAG.ie9e3cbe2153e2cf5bcd7ff84eec2f77b.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, доставкой занимает я маркетплейс, к сожалению не можем повлиять на скорость доставки.\nПриносим свои извинения за доставленные неудобства.",
              "addTimestamp": 1759732486514
            }
          },
          {
            "chatID": "1:8354eff6-3771-83ce-7ed5-87cf3d94d0cb",
            "replySign": "1:8354eff6-3771-83ce-7ed5-87cf3d94d0cb::3f792de778a47f3d27386953f63f9437da97b363210e43067d5fe4628441f9b3ab46d5f1e1674be2a8838797982cc6b1dd8d34dd42236ce6b49428c5e27e4713",
            "clientID": "",
            "clientName": "Алексей",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 332745174,
              "price": 0,
              "priceCurrency": "",
              "rid": "7038715393024509731.3.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Доброго вечера , так как заказ задерживается уже на три дня и продолжает задерживаться ч вынужден отказаться от вашего краника, не один нормальный человек не будет ждать больше недели задержки заказанного товара, ч уже давно купил в магазине и установил краник, так что разбирайтесь с валберис , вы теряете деньги из за доставки валберис",
              "addTimestamp": 1758736217808
            }
          },
          {
            "chatID": "1:b729b9a3-3b21-8b5a-082f-93d4a6ed9fcf",
            "replySign": "1:b729b9a3-3b21-8b5a-082f-93d4a6ed9fcf::5cf51d1fe76bae81d5103e44066dcaee30d1365193a7f2091fc9406bbc4bca22ec6136764af32eb1d422f95c98ac981d8d65b3338835a93b7e319a0f683aafab",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 335244089,
              "price": 0,
              "priceCurrency": "",
              "rid": "7558225781965755335.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Где товар",
              "addTimestamp": 1757846918448
            }
          },
          {
            "chatID": "1:f3d51142-b5bd-8bdf-aacc-334a81579cf6",
            "replySign": "1:f3d51142-b5bd-8bdf-aacc-334a81579cf6::2053d740e69ea54afd51e3433ef808d1b8a97461f8a5fc0ad7015cab475bb810567ab17141bd7db69bcc49356a921c64b21bb29698ac06748ac6cdb753947e75",
            "clientID": "",
            "clientName": "Юрий",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 356872875,
              "price": 0,
              "priceCurrency": "",
              "rid": "8550220378024349308.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Факт обмана опровергаем, на складе произошел пересорт.\nКлапан является регулируемым, вы можете настроить на 1,5 бара и использовать его.\nЕсли такой вариант вас не устраивает, товар можете вернуть.\n",
              "addTimestamp": 1756736530889
            }
          },
          {
            "chatID": "1:7c459268-aeb0-8e03-311b-37963ee56557",
            "replySign": "1:7c459268-aeb0-8e03-311b-37963ee56557::2fc666265734b300c38ba58b8a220c38a9ba90644d63ecc897e2c2caff94f3d1cbf6ed6daf95b43ddfd747143bbbcfd330ed3dca0942fad37cca8b58e4251a16",
            "clientID": "",
            "clientName": "Антон",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 356857944,
              "price": 0,
              "priceCurrency": "",
              "rid": "d5.r66f838c361c743a9addb00611b7f2354.0.5",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Расходомер идёт без ответной части",
              "addTimestamp": 1756709999643
            }
          },
          {
            "chatID": "1:d4504c3b-02fb-6bb6-bdfb-1ee46abaae81",
            "replySign": "1:d4504c3b-02fb-6bb6-bdfb-1ee46abaae81::b138b2ec9b49dbda69e6945225e2deffe794844e7bf44c245790b716370c3cdb85bd538a5f8d93347b6f606e0ac4cfafc86da1525d19fdb18b1901bab265ddbb",
            "clientID": "",
            "clientName": "Светлана",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544508,
              "price": 0,
              "priceCurrency": "",
              "rid": "6123402332514964021.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Гарантия действительна с даты покупки.",
              "addTimestamp": 1756709964954
            }
          },
          {
            "chatID": "1:80af78ed-c10d-cce4-f196-2a468f6392ac",
            "replySign": "1:80af78ed-c10d-cce4-f196-2a468f6392ac::d4f94fa439647152e9e6366eb786a1b1ec75a645301970df950a93585f49107da91c52c0470fcda709ca84b5effa111eb0e3ba45420944e9454ab283a77c314e",
            "clientID": "",
            "clientName": "Антон",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 356857944,
              "price": 0,
              "priceCurrency": "",
              "rid": "d5.r66f838c361c743a9addb00611b7f2354.0.6",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Добрый день. Ответная часть находится в коллекторе.",
              "addTimestamp": 1755582962093
            }
          },
          {
            "chatID": "1:0db0157a-610c-15c4-67cc-8c093c04d008",
            "replySign": "1:0db0157a-610c-15c4-67cc-8c093c04d008::73057365aae5b34bf533ac39f1b4c25863280933a71d2fc190cc5ca691d023f9a37c14bd1b7dd383f3a84e9bdd3661826eaf4423109eb324b9836fc371e1480c",
            "clientID": "",
            "clientName": "Алина",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586812,
              "price": 0,
              "priceCurrency": "",
              "rid": "d6.r8ab41f37bb314fac955d0f9d0654701a.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Доставкой товара занимается непосредственно маркетплейс, и сам регламентирует время доставки, к сожалению не имеем возможности на нее влиять.",
              "addTimestamp": 1754241961019
            }
          },
          {
            "chatID": "1:3ecf67e2-07b2-c3c0-78e3-452019df959d",
            "replySign": "1:3ecf67e2-07b2-c3c0-78e3-452019df959d::63c586f59c0f4ca975f4623b57e4f5c1ce9d5012de0f8a4c747f56927317357092be405f2720c210052518fd4bd44f9264a047a5a74219e9dd4009b68e00dab7",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 428211698,
              "price": 0,
              "priceCurrency": "",
              "rid": "5456247473043109280.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Добрый день. Мы не имеем возможности самостоятельно отменять заказы клиентов, не предполагает площадка.\nОбратитесь в поддержку для клиентов, вам помогут.",
              "addTimestamp": 1753961463782
            }
          },
          {
            "chatID": "1:371ed06f-44a4-bc93-1ac6-fd5d9ec24d32",
            "replySign": "1:371ed06f-44a4-bc93-1ac6-fd5d9ec24d32::ee8da4743b53cd5e9ac7ba3176f78d40f45e84764d4c567c3673edc87d1560a262fd8b9296b11eb80814c6bc685392b5cfc8b67946e7a28cc3e6b2640768e678",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586280,
              "price": 0,
              "priceCurrency": "",
              "rid": "7729853225886781682.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Благодарим за Ваше обращение. Если заказ оформили буквально недавно, то проследуйте по следующей Инструкции: зайти в раздел \"Доставки\" -> под карточкой нужного товара кнопка \"Оформлен\" -> \"Отменить заказ\" -> \"Да, отменить\". Желаем Вам всего доброго. С уважением, представитель бренда ZEGOR.",
              "addTimestamp": 1752775254145
            }
          },
          {
            "chatID": "1:2eef0aa2-b9a3-ac5a-7ff5-e6d32a0d7766",
            "replySign": "1:2eef0aa2-b9a3-ac5a-7ff5-e6d32a0d7766::692af5e42743c49fa015c1d3db4dd05d8d274e608438ad8d6e8417bca914de803d8945b212dedb9538ac873fcd7773ded4efb69466b243fc116698547d5c90b7",
            "clientID": "",
            "clientName": "Исакович Анна Витальевна",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 331719662,
              "price": 0,
              "priceCurrency": "",
              "rid": "6440102393704466040.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Заказывала 2 крана",
              "addTimestamp": 1752132333061
            }
          },
          {
            "chatID": "1:edc3c567-d211-f39a-4d42-6a66fe590b5a",
            "replySign": "1:edc3c567-d211-f39a-4d42-6a66fe590b5a::ff865c30734691b94a4729bd71a3c3dd8b55cc329fcde1cc517b18a43ac85b49919ef746915fd5f6d6ff13a38c501d67d11dfae0aba2dad789cb056f1a63c2fe",
            "clientID": "",
            "clientName": "Анатолий",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 381086465,
              "price": 0,
              "priceCurrency": "",
              "rid": "5472898163481752550.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Главное чтобы Манометр был целый и упаковка не нарушена",
              "addTimestamp": 1751703487863
            }
          },
          {
            "chatID": "1:15128b57-b251-b7af-ec8b-fcfa9e6b4d9a",
            "replySign": "1:15128b57-b251-b7af-ec8b-fcfa9e6b4d9a::0c00b75494541196046973280a3dfd4b3bce6b7b04304bb926e3a19261d6bdfcc169a25590d77b2baeaba794a37d0c81c08dee182f7781dc378eeeefca641cdd",
            "clientID": "",
            "clientName": "Алексей",
            "goodCard": {
              "date": "2025-06-20T13:38:02Z",
              "nmID": 401884254,
              "price": 42300,
              "priceCurrency": "RUB",
              "rid": "15666183610190941.0.0",
              "size": "0",
              "statusID": 1
            },
            "lastMessage": {
              "text": "Здравствуйте, Вы можете отменить заказ самостоятельно, к сожалению мы не имеем возможности отменять заказы клиентов. \nЕсли возникнут трудности, обратитесь к техподдержке вайлдберриз.",
              "addTimestamp": 1750541665911
            }
          },
          {
            "chatID": "1:71d960f7-9352-3748-daba-d03e9a7f6948",
            "replySign": "1:71d960f7-9352-3748-daba-d03e9a7f6948::baa96e151fd92bb4776ccb759e44bf5d103ff47926efaee0f04e25edcc366b77ae6f71b2a56269013d75906524aae95eeae345186f1656c8638cc8d5a910a74f",
            "clientID": "",
            "clientName": "Алексей",
            "goodCard": {
              "date": "2025-06-20T13:38:02Z",
              "nmID": 401884254,
              "price": 42300,
              "priceCurrency": "RUB",
              "rid": "15666183610190941.0.1",
              "size": "0",
              "statusID": 1
            },
            "lastMessage": {
              "text": "Здравствуйте, Вы можете отменить заказ самостоятельно, к сожалению мы не имеем возможности отменять заказы клиентов. Если возникнут трудности, обратитесь к техподдержке вайлдберриз.",
              "addTimestamp": 1750541652690
            }
          },
          {
            "chatID": "1:bd746c35-94e3-329a-07cd-1bf7479e7722",
            "replySign": "1:bd746c35-94e3-329a-07cd-1bf7479e7722::f20e316c9f20ba97ae6c46349b570afcd2cab75d2b9ae3a43211f853735274f4e7e998c75f3aacf42a66cfe1a102b252f3a67f6c2a5639011df7f37ba9962014",
            "clientID": "",
            "clientName": "Петр",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586280,
              "price": 0,
              "priceCurrency": "",
              "rid": "6521581139672999195.1.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, возврат одобрили.",
              "addTimestamp": 1750362998048
            }
          },
          {
            "chatID": "1:fcb9eaac-5a0d-f8cd-15e6-8f99815ec5f4",
            "replySign": "1:fcb9eaac-5a0d-f8cd-15e6-8f99815ec5f4::d04ef6e97ad1b5a56fa72e2b2e9289bca9058351bed0cde4ca0296b13b311079db78f7c267de269bd609eeb8dcfc9dd37b1e7a7547d9b5f07731652905385746",
            "clientID": "",
            "clientName": "Дмитрий",
            "goodCard": {
              "date": "2025-05-17T17:26:34Z",
              "nmID": 331936730,
              "price": 39400,
              "priceCurrency": "RUB",
              "rid": "d0.9b75f1bc18b844c2b0b790525b2c9ebb.0.0",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Здравствуйте. Какой вопрос?",
              "addTimestamp": 1749295147462
            }
          },
          {
            "chatID": "1:65708585-8d4b-7e3c-5525-2612abeca32e",
            "replySign": "1:65708585-8d4b-7e3c-5525-2612abeca32e::5779de4cca27c7ff5f7fdc2e4b03e8da69bfd6b151c61c6b63261eb5f6ab9edc4b30b3c45cde1f57758e53a9362d3589e08f30041201021005e8460dcb11c237",
            "clientID": "",
            "clientName": "Елена",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 252586296,
              "price": 0,
              "priceCurrency": "",
              "rid": "11034227608816433.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Коробку можете выкинуть через 2 недели после установки.",
              "addTimestamp": 1749295111806
            }
          },
          {
            "chatID": "1:bb314ddd-1085-9964-1b00-180a9e6c8b19",
            "replySign": "1:bb314ddd-1085-9964-1b00-180a9e6c8b19::8cdc05e1a21948be3f2da2aa54a7bdd62cbf869f4031f149b42511611c6f77e658ae2132cef654410364cccdeebc15a0e666a44ba84499dacd165df51cbff589",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 360755496,
              "price": 0,
              "priceCurrency": "",
              "rid": "d3.re3f2563a06c8443789f5c6fef1cc0270.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте! Здесь вы можете задать вопросы по возврату товара, если они у вас возникнут",
              "addTimestamp": 1748322586574
            }
          },
          {
            "chatID": "1:5db3b9e3-7ab1-ba43-0f97-aacc0ac9cc34",
            "replySign": "1:5db3b9e3-7ab1-ba43-0f97-aacc0ac9cc34::aee619816568ef5bc443323f4d139411da16d669fdb89774573691f4af8920423c67d6d344695c18b232bc3ec99bf56f748e2ee56e305ee843d84cb1f5dc6593",
            "clientID": "",
            "clientName": "Оксана",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 381086465,
              "price": 0,
              "priceCurrency": "",
              "rid": "8498959629396975561.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, возврат подтверждаем, будем разбираться на производстве.",
              "addTimestamp": 1746967864639
            }
          },
          {
            "chatID": "1:c2144705-8769-8109-16d0-7feb6512c075",
            "replySign": "1:c2144705-8769-8109-16d0-7feb6512c075::5d7b3cf658c4dda98cb369b83e399e89a5911b3ad99d32cbce2cf75f7be1573c3395bc5920ad29191963f80c98c7b64411cd6ff7a554a3b23ace15e6a746544e",
            "clientID": "",
            "clientName": "Тамара",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544513,
              "price": 0,
              "priceCurrency": "",
              "rid": "4623933431212927764.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, насос захватил песок вместе с водой, по инструкции его необходимо было поднять минимум 1,5 м от дна. \nДанный случай не является гарантийным.",
              "addTimestamp": 1746967707280
            }
          },
          {
            "chatID": "1:0d1ff1c1-f435-449a-6e62-bfe2d7607eea",
            "replySign": "1:0d1ff1c1-f435-449a-6e62-bfe2d7607eea::a5d2b46b51a36520ad458e82f955bae6a65d2cf55171791c20174fdfb776d39f639e55f5a7441f205782bb1b882d60575514ed2d06034f677ae5e51cd1b0ff79",
            "clientID": "",
            "clientName": "Владимир",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586280,
              "price": 0,
              "priceCurrency": "",
              "rid": "6561821447063152496.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Один из сифонов, т.е. один лишний!",
              "addTimestamp": 1746551200822
            }
          },
          {
            "chatID": "1:58f218a2-27b9-ea32-2007-cfbbca7d7a7e",
            "replySign": "1:58f218a2-27b9-ea32-2007-cfbbca7d7a7e::7c34e64a687475e526fa83ef27d397c0df161d937e523e6cad1644acf0df6bf1b12501824a2a24551d8f758bd1c061214dcadf1b1618f7b0b6f6a9ad232ffe6e",
            "clientID": "",
            "clientName": "Сергей",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 360755496,
              "price": 0,
              "priceCurrency": "",
              "rid": "dv.8983e7b9028049629a4a3ab592598b2c.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "хочу вернуть реле, потому что пришло сломаное",
              "addTimestamp": 1746198293439
            }
          },
          {
            "chatID": "1:49f57983-d801-c46e-83db-0d019cf5e80a",
            "replySign": "1:49f57983-d801-c46e-83db-0d019cf5e80a::0f1b9b0b81178e018502188846931c93700bfd4dda895e31954a934b91f9b842a7e69f22e1f465c41fe193edf5d333ccd24757b04d35a43015271252245ec31b",
            "clientID": "",
            "clientName": "Елена",
            "goodCard": {
              "date": "2025-04-23T06:56:02Z",
              "nmID": 233586811,
              "price": 39800,
              "priceCurrency": "RUB",
              "rid": "c8f7532bdb8a4b97b37b8b77920556bd",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Слушайте! Имейте совесть! Где товар???",
              "addTimestamp": 1745895477433
            }
          },
          {
            "chatID": "1:76158562-b657-1560-83c2-5df5caa9b93a",
            "replySign": "1:76158562-b657-1560-83c2-5df5caa9b93a::c25f8e74afa55021b870329b7f6d126fe96974e602a65d8b73cb60acdca186d685cebcbd8d965fcac7239a4f1e504258131e7d8554327291e72263ace665c2bd",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 252586295,
              "price": 0,
              "priceCurrency": "",
              "rid": "4754350563869886463.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте. Данная царапина на корпусе была обнаружена после того как вы забрали изделие с ПВЗ, Правилами  маркетплейса предусмотрено, что вы должны осмотреть товар перед тем как его забрать с пункта выдачи.\nМы всегда принимаем к возврату изделия, где обнаружен заводской брак или неисправность в работе товара.\nПри этом товар является полностью технически исправным, соответственно это не заводской брак. \nВернуть его производителю по причине брака невозможно.",
              "addTimestamp": 1745854826805
            }
          },
          {
            "chatID": "1:62d1f2c5-4e75-d34c-1d76-75a18da7edd8",
            "replySign": "1:62d1f2c5-4e75-d34c-1d76-75a18da7edd8::5774d69256dff2b6f4f15a5fb98b2fedb7fdd1b0d71ec4aaa94cc1b1e7a0fb461df70cef1dbd4d41dbc2e605f32655418acc7a9feba11dd815696b7b9a33c8ab",
            "clientID": "",
            "clientName": "Юлия",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233561764,
              "price": 0,
              "priceCurrency": "",
              "rid": "6652141906125590408.1.3",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "мы из Рязани",
              "addTimestamp": 1745744335773
            }
          },
          {
            "chatID": "1:6cde1f9b-3698-be87-2a67-f7212a8a89c0",
            "replySign": "1:6cde1f9b-3698-be87-2a67-f7212a8a89c0::bbcd06b3a66736d81b9dad26cc4108d0db0427f6d8498ce325e910af6c55c8b2fdd98f5ef5a1d813b10c860f2df1e2c4452ce17db10eb58b11c528c4e2cb714d",
            "clientID": "",
            "clientName": "Людмила",
            "goodCard": {
              "date": "2025-04-19T17:59:14Z",
              "nmID": 360755496,
              "price": 74200,
              "priceCurrency": "RUB",
              "rid": "dM.e4aa88dd5fed498a883eac392a2122a5.0.0",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Здравствуйте! У меня вопрос по товару \"Реле давления 1\" 1,4-2,8 бар (со встроенным манометром), бренд Zegor, артикул 360755496, товар оформлен 19.04.2025\" , скажите пожалуйста  а где мой заказ который должен был придти 25 апреля ????",
              "addTimestamp": 1745688034000
            }
          },
          {
            "chatID": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d",
            "replySign": "1:67d39c4b-d2f7-c146-b5c3-dc8fa9f5126d::a537fe28ce9580ea1aa2ad68b9a3a2fa749d3ba8afab1a2ff7927a29e2f78bd194d90de585a8a0e23a5cbf822bfa7c054c327f164ea9bb57f8b4e99910292764",
            "clientID": "",
            "clientName": "Валентин",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544510,
              "price": 0,
              "priceCurrency": "",
              "rid": "7117333302831323250.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Просканировали данный код, Woman fashion bot, к сожалению мы не имеем отношения к данному боту. Рекламная продукция не наша.\n\nНи один из наших клиентов с данной просьбой и фото кода к нам не обращался. Это относится к категории одежда. Мы данной категорией товаров не занимаемся.\n\nВы можете задать вопрос техподдержке Вайлдберриз.\n",
              "addTimestamp": 1745686079578
            }
          },
          {
            "chatID": "1:4d18107c-626a-3e61-e6b4-57483ddec368",
            "replySign": "1:4d18107c-626a-3e61-e6b4-57483ddec368::1e7867c72fcb11b5e9287c6a6faa2f909248758c60f165dcbc9922083832d6935807dcf1bdf288268fad1fe0db251b61d1e6b59ab81be1ac823ece9e3e20e46e",
            "clientID": "",
            "clientName": "Алексей",
            "goodCard": {
              "date": "2025-04-19T05:12:35Z",
              "nmID": 233544512,
              "price": 229200,
              "priceCurrency": "RUB",
              "rid": "dw.fd4082a6a971449fb9e9f9bbc3aec60b.0.0",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Здравствуйте, мы не можем влиять на доставку и регламентировать ее срок, так как этим вопросом занимается непосредственно маркетплейс и рассчитывает ее автоматически. Вы можете обратиться в клиентскую поддержку маркетплейса.",
              "addTimestamp": 1745521655458
            }
          },
          {
            "chatID": "1:7dd73f8f-d19e-3d29-25d0-33641530716c",
            "replySign": "1:7dd73f8f-d19e-3d29-25d0-33641530716c::fb292787ca8d61a2b3a0a4702effb454668ad52c0b9871367e01386e13fa9cd36278093c9d6df15480477702832fd2842e3ce3bbf866af43ab8b32b325d3764e",
            "clientID": "",
            "clientName": "Сергей",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 360755496,
              "price": 0,
              "priceCurrency": "",
              "rid": "5753959077382472422.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Добрый день. Подскажите, заводская упаковка сохранена и внешний вид товара не поврежден? Отправьте пожалуйста фото. Если все в порядке, без проблем согласуем возврат.",
              "addTimestamp": 1745501896824
            }
          },
          {
            "chatID": "1:5465b6e1-dd53-837e-a612-0d279168601e",
            "replySign": "1:5465b6e1-dd53-837e-a612-0d279168601e::e599e7a9e9965a440af3aadf4bfb37dec1a9b2a45946b6cba7854cf5e4b7a473f90bc4a29c0ec00958a68f10bbcc4b5d8117bc4d84ac5429e6580c05128c6235",
            "clientID": "",
            "clientName": "Алптухан",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544512,
              "price": 0,
              "priceCurrency": "",
              "rid": "103868489606575313.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Верно, только воду чистую качает.",
              "addTimestamp": 1745427110104
            }
          },
          {
            "chatID": "1:a3a525a7-39e0-2bee-a687-d08b09c43fb9",
            "replySign": "1:a3a525a7-39e0-2bee-a687-d08b09c43fb9::07b1174e01e0d161d38bea142b587fa4bdb2e5feb9c6bc6260d27a5f2b6eef5fee9f7b533b84b660364b46d87cbe5bcf8459982d505ad5233fc63f2a7d5447d9",
            "clientID": "",
            "clientName": "Кирилл",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233586279,
              "price": 0,
              "priceCurrency": "",
              "rid": "4725843691133682638.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Возврат одобрен.",
              "addTimestamp": 1745317851339
            }
          },
          {
            "chatID": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da",
            "replySign": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da::2f46781225e315cc2a8cb43107e9fff4fa510fc0a8974f756bf4b00220d7b1fe5d0a501c2875dbbab0c79c32affdec4dbdf18546c7b395df3520f94b35de02a1",
            "clientID": "",
            "clientName": "Игорь",
            "goodCard": {
              "date": "2025-04-12T19:06:45Z",
              "nmID": 331463403,
              "price": 39700,
              "priceCurrency": "RUB",
              "rid": "dL.9c4a05d5e5b04858b8a788c6ed5e59dd.0.0",
              "size": "0",
              "statusID": 3
            },
            "lastMessage": {
              "text": "Вчера кран доставили. Спасибо за участие.",
              "addTimestamp": 1745227129394
            }
          },
          {
            "chatID": "1:2a1f5d20-9396-3470-d221-928abe528ceb",
            "replySign": "1:2a1f5d20-9396-3470-d221-928abe528ceb::e88a256d9fed015fb2f9c670787d10417a87567c1701c3254a4ec5a1929f8ee57273a5ae2033c464bd5dc01377cd789733f71dcebf7992002ca5c0c3b0f64a63",
            "clientID": "",
            "clientName": "",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 335244089,
              "price": 0,
              "priceCurrency": "",
              "rid": "d1.r660441ceb5c7414c9f1fc197e1a7bb2e.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Здравствуйте, напишите в клиентскую поддержку вайлдберриз, мы к сожалению не имеем возможности отследить такие моменты. Доставкой занимается вайлдберриз.",
              "addTimestamp": 1745174263997
            }
          },
          {
            "chatID": "1:4dcea925-5020-1adf-f56e-9b89d29bb4e2",
            "replySign": "1:4dcea925-5020-1adf-f56e-9b89d29bb4e2::da1c4e5e88fbef7a61e93ae6a8791d0a137acf4533902b444563981ba6251b47bf76548bad0b84a7df9d3b4326056e2b723ec6decc17a26321692325adf5ada7",
            "clientID": "",
            "clientName": "Екатерина",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544512,
              "price": 0,
              "priceCurrency": "",
              "rid": "5408924234529097905.0.0",
              "size": "",
              "statusID": 0
            },
            "lastMessage": {
              "text": "Видимо песок или камень попал внутрь.\nВозврат одобряем.",
              "addTimestamp": 1744126064239
            }
          },
          {
            "chatID": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f",
            "replySign": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f::c4cc61a8d99c85fca0da346776b623eb6f6a01dec8a8358aa08e1f8bcb170fccdbbd3faac2d9c8fdf43060f4aeb1506c7f4a31159e2733643674473b94ad5e4f",
            "clientID": "",
            "clientName": "Олег",
            "goodCard": {
              "date": "0001-01-01T00:00:00Z",
              "nmID": 233544511,
              "price": 207500,
              "priceCurrency": "RUB",
              "rid": "e0aa90b5957442d2ba373900503226b4",
              "size": "0",
              "statusID": 0
            }
          }
        ],
        "errors": null
      },
      "content_type": "application/json; charset=utf-8"
    }
  ],
  "summary": {
    "success_count": 3,
    "total_count": 3,
    "success_rate": "3/3",
    "all_passed": true
  }
}
```

### Test Token Details
```json
{
  "token_name": "Test",
  "timestamp": "2026-02-09T12:16:02.002644",
  "jwt_payload": {
    "acc": 2,
    "ent": 1,
    "exp": 1786396376,
    "id": "019c41ac-e7a0-7cdd-ab2b-e803ce0923d5",
    "iid": 44511123,
    "oid": 4112188,
    "s": 0,
    "sid": "764bb5eb-b610-427d-b167-904935fde848",
    "t": true,
    "uid": 44511123
  },
  "tests": [
    {
      "endpoint": "/api/v1/seller/chats",
      "method": "GET",
      "status_code": 401,
      "success": false,
      "response_time_ms": 1323,
      "response_body": {
        "title": "unauthorized",
        "detail": "token scope not allowed",
        "code": "461a0b83d6bd a53a3d31f8b003bce 8d7a4aaab17a",
        "requestId": "4a36923593a61f24796c33ff3a8cd79e",
        "origin": "s2s-api-auth-chatx",
        "status": 401,
        "statusText": "Unauthorized",
        "timestamp": "2026-02-09T09:16:02Z"
      },
      "content_type": "application/problem+json"
    },
    {
      "endpoint": "/api/v1/seller/events",
      "method": "GET",
      "status_code": 401,
      "success": false,
      "response_time_ms": 660,
      "response_body": {
        "title": "unauthorized",
        "detail": "token scope not allowed",
        "code": "461a0b83d6bd a53a3d31f8b003bce 8d7a4aaab17a",
        "requestId": "d346edcf318f7cd2682682564e534d17",
        "origin": "s2s-api-auth-chatx",
        "status": 401,
        "statusText": "Unauthorized",
        "timestamp": "2026-02-09T09:16:03Z"
      },
      "content_type": "application/problem+json"
    },
    {
      "endpoint": "/api/v1/seller/chats",
      "method": "GET",
      "status_code": 401,
      "success": false,
      "response_time_ms": 657,
      "response_body": {
        "title": "unauthorized",
        "detail": "token scope not allowed",
        "code": "461a0b83d6bd a53a3d31f8b003bce 8d7a4aaab17a",
        "requestId": "8fedfcd0b850053d58a78c38ecc5192c",
        "origin": "s2s-api-auth-chatx",
        "status": 401,
        "statusText": "Unauthorized",
        "timestamp": "2026-02-09T09:16:04Z"
      },
      "content_type": "application/problem+json"
    }
  ],
  "summary": {
    "success_count": 0,
    "total_count": 3,
    "success_rate": "0/3",
    "all_passed": false
  }
}
```
