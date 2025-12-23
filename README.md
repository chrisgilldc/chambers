<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a id="readme-top"></a>
<!--
*** Thanks for checking out the Best-README-Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Don't forget to give the project a star!
*** Thanks again! Now go create something AMAZING! :D
-->



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![GPL-3.0 License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]



<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/chrisgilldc/chambers">
    <img src="images/Seal_of_the_United_States_Congress.svg" alt="Logo" width="80" height="80">
  </a>

<h3 align="center">Chambers</h3>

  <p align="center">
    Current status of the U.S. Congress
    <br />
    <a href="https://github.com/chrisgilldc/chambers"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/chrisgilldc/chambers">View Demo</a>
    &middot;
    <a href="https://github.com/chrisgilldc/chambers/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/chrisgilldc/chambers/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

Chambers collects data from multiple sources to provide near-real-time status of the House of Representatives and the Senate.

This is available as a pip-installable library and as an Add-On to Home Assistant.

House data is collected from the Clerk of the House's Floor Proceeding XML files. These are updated frequently throughout
the day while the House is in session.

Senate data is collected from the Senate's LIS Floor Activity XML and the Floor Schedule JSON. The Senate's XML data is
generally only available for the previous day. The JSON is a snapshot of the current proceedings. This data is merged to
determine current status.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->
## Getting Started

### Library Installation

Package can be installed simply via pip into your python environment.

```
pip install chambers
```

If you want the latest and greatest development version, install from the github dev branch

```
pip install git+https://github.com/chrisgilldc/chambers@dev
```

Either way, all required packages should be installed by pip.

### Add-On Installation

Add the Github URL to Home Assistant.

Install.

Boom.

## Usage

### Library Usage

Import the library and instantiate an object of the appropriate type.

```
import chambers
house_object = chambers.House()
senate_object = chambers.Senate()
```
Both objects take an optional 'tz' parameter which will set the default timezone for all output from the object. 
TZ should be a valid timezone string (ie: 'Asia/Tokyo', 'Europe/Berlin', etc). If not set, system timezone will be used.

Each object has common methods and properties 

Property:
* convened - Is the chamber in session? Either true or false.

Methods:
* update() - Updates the chamber's data from sources if next update time has come. Include force=True to update no matter what. Returns True if data was loaded, False if not.
* convened_at() - If convened, datetime of when the chamber convened, otherwise None.
* convenes_at() - If not convened, datetime of when the chamber is scheduled to convene, otherwise None.
* adjourned_at() - If not convened, datetime of when the chamber adjourned, otherwise None.

All the _at() methods accept an optional 'tz' parameter to override the object's default timezone for output.

```
>>> house_object.update()
2025-07-06 08:33:39,847 - House - INFO - No events available at update. Loading.
2025-07-06 08:33:46,295 - House - INFO - Found floor proceedings for 02 Jul 2025. Loading.
2025-07-06 08:33:46,424 - House - INFO - Event H61000 - Adjournment
2025-07-06 08:33:46,457 - House - INFO - Event H20100 - New Legislative Day.
2025-07-06 08:33:46,460 - House - INFO - Processed all floor actions.
2025-07-06 08:33:46,463 - House - INFO - Loaded 9 events from journal on 02 Jul 2025
2025-07-06 08:33:46,468 - House - INFO - Sorting events.
2025-07-06 08:33:46,471 - House - INFO - Load complete.
True
>>> house_object.convened_at
>>> house_object.convenes_at
datetime.datetime(2025, 7, 7, 10, 0, tzinfo=zoneinfo.ZoneInfo(key='America/New_York'))
>>> house_object.adjourned_at
datetime.datetime(2025, 7, 3, 14, 33, 17, tzinfo=zoneinfo.ZoneInfo(key='America/New_York'))
```
<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Add-On Usage

For each chamber, four entities are created:
* Convened - Is the chamber currently convened?
* Convened At - When the chamber convened, if it is. Otherwise unknown.
* Convenes At - If adjourned, when the chamber is scheduled to convene. Otherwise, unknown.
* Adjourned At - If adjourned, when the chamber adjourned. Otherwise, unknown.

A 'Running' sensor for the Add-on is also provided.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Daemonization

An MQTT daemon, 'chamber-watcher', is also installed as part of the package, intended for use by the Home Assistant 
add-on, although it should work stand-alone.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- ROADMAP -->
## Roadmap

- [ ] Allow logging to be suppressed during updates. May not be desirable for library use.
- [ ] Refine 'activity' method for the House to allow more detailed current activity.
- [ ] A more granular 'convene' that considers recesses.

See the [open issues](https://github.com/chrisgilldc/chambers/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->
## Contributing

This is one of my first public projects so I won't claim I have any great knowledge or skill in accepting or managing contributions.
That said, any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/chrisgilldc/chambers/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=chrisgilldc/chambers" alt="contrib.rocks image" />
</a>

<!-- LICENSE -->
## License

Distributed under the GPL-3.0-or-later. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/chrisgilldc/chambers.svg?style=for-the-badge
[contributors-url]: https://github.com/chrisgilldc/chambers/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/chrisgilldc/chambers.svg?style=for-the-badge
[forks-url]: https://github.com/chrisgilldc/chambers/network/members
[stars-shield]: https://img.shields.io/github/stars/chrisgilldc/chambers.svg?style=for-the-badge
[stars-url]: https://github.com/chrisgilldc/chambers/stargazers
[issues-shield]: https://img.shields.io/github/issues/chrisgilldc/chambers.svg?style=for-the-badge
[issues-url]: https://github.com/chrisgilldc/chambers/issues
[license-shield]: https://img.shields.io/github/license/chrisgilldc/chambers.svg?style=for-the-badge
[license-url]: https://github.com/chrisgilldc/chambers/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/linkedin_username
[product-screenshot]: images/screenshot.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vue.js]: https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D
[Vue-url]: https://vuejs.org/
[Angular.io]: https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white
[Angular-url]: https://angular.io/
[Svelte.dev]: https://img.shields.io/badge/Svelte-4A4A55?style=for-the-badge&logo=svelte&logoColor=FF3E00
[Svelte-url]: https://svelte.dev/
[Laravel.com]: https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white
[Laravel-url]: https://laravel.com
[Bootstrap.com]: https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white
[Bootstrap-url]: https://getbootstrap.com
[JQuery.com]: https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white
[JQuery-url]: https://jquery.com 
