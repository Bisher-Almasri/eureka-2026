# Locked In

Locked In  AI-powered personalized learning and code assistance that makes sure your Locked In.

## Inspiration
The main sources of inspiration were Jarvis and W3 Schools. We were inspired by W3 Schools containing tailored code lessons through step by step instructions for every programming language. This is why our app performs the same function, except instead of just programming, it can teach its users anything, broken down step by step. We were also inspired by Jarvis, the fictional Marvel voice assistant for Iron Man.

## What it does
The app allows users to create customized lessons. This ranges from any topic, and creates quizzes and tests to accommodate the user and their preferred learning style. The anti-procrastinating aspect of the device incorporates an ESP32 and OrangePi to track the user, if the user is found to be procrastinating,  the device beeps and warns the user through LEDs. Furthermore, if the user has left the work area, the device recognizes this using its sensors and warns the user through beeps and bright LEDs. The camera watches the user, making sure they are facing towards the screen and it tracks your browser to make sure you are on the right websites.  Another feature we have called Hydra Mode was inspired by the fictional creature from Greek mythology. It ensures you’re staying on track by telling you to get back to work. Our App allows users to directly communicate with the device using voice activation. Not only does it provide convenience for all users, it can provide full accessibility for handicapped users. 


## How we built it
We have built it with python with textual. We did image recognition using numpy and opencv. We used opencv to detect objects and numpy to detect them moving and focusing. We also used an OrangePi and an ESP32 module to detect movement and buzzer sounds.

## Challenges we ran into
We ran into ESP32 connection challenges, challenges using the correct voltage for ESP32 Parts, challenges with our libraries for the ESP32 not installing and loading properly, and challenges with our cache for the ESP32. Furthermore, we spent a lot of time troubleshooting with the OrangePi Camera, since it had a lot of latency and troubles communicating to the study website and sending data to the files, even though we were able to send data from the Pi to the Mac.

## Accomplishments that we're proud of

Locked In was able to track active chrome tabs on an user’s device through process-ID managers. We were also able to identify all the active processes on a user’s device and categorized them as either productive or distraction. We were able to use Open CV, numpy, and media pipe to handle eye and face detection.

## What we learned

We learnt communication is key and to always plan our next steps. Without planning our next steps we were stuck and didn't know where to go and what to do, and without communication we didn't know what was finished like how to implement the hardware to the software. When we ran into trouble with the ESP32 we considered alternative solutions, but at the end after some logic analysis, we decided that the best course of action was to alter our code slightly to get the correct output. From this, we learned to trust our instincts and approach the same problem with different perspectives.

## What's next for Locked in
We plan on adding more language support for code blocks and support for quizzes for non-code projects. We would also like to improve our AI User learn modal to make it more accurate and better. We could also implement an agenda or a calendar feature to track your work.
